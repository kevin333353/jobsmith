"""① Supervisor Agent：用 LLM 動態調度（取代寫死的 if 門檻），失敗時回門檻備援。

兩個決策點：
- supervise_after_match：看匹配報告決定 proceed / stop。
- supervise_after_critic：看品管評審決定 approve / revise，並指定 docs_to_revise。

設計重點（履歷賣點）：路由由 LLM 判斷並附 rationale，而非單一 if；但 LLM 失敗 / 逾時 /
回傳不合法時，一律退回確定性門檻邏輯，確保流程永遠能走（production-grade 的保底）。
"""
from __future__ import annotations

from app.llm import get_llm
from app.models import (
    MatchReport, CritiqueReport, ParsedJob, Profile, SupervisorDecision,
)

PROCEED_SCORE_THRESHOLD = 60
_DOC_PASS = 75
_ALL_DOCS = ("resume", "cover_letter", "interview")

SUP_MATCH_SYSTEM = (
    "你是多 agent 求職系統的調度主管。根據匹配報告與職缺，判斷是否值得花算力產出整份投遞包。"
    "next_action 只能是 proceed（值得續做）或 stop（適配太低、不值得）。"
    "高適配或雖有落差但可補強 → proceed；明顯不符、硬性條件缺太多 → stop。請附簡短 rationale。"
)

SUP_CRITIC_SYSTEM = (
    "你是多 agent 求職系統的調度主管。根據品管評審結果，決定 next_action："
    "approve（品質夠好，送人工核可）或 revise（需要再改）。"
    "若 revise，docs_to_revise 只列出真正需要重寫的文件（resume / cover_letter / interview），"
    "已達標的不要列，以免浪費算力重跑。請附簡短 rationale。"
)


def _match_fallback(match: MatchReport) -> SupervisorDecision:
    proceed = match.recommend_proceed and match.score >= PROCEED_SCORE_THRESHOLD
    return SupervisorDecision(next_action="proceed" if proceed else "stop",
                              rationale="（門檻備援）")


def _critic_fallback(critique: CritiqueReport) -> SupervisorDecision:
    if critique.overall_pass:
        return SupervisorDecision(next_action="approve", rationale="（門檻備援）整體達標")
    docs = [d for d in (critique.per_doc or {}) if d in _ALL_DOCS]
    if not docs:  # 模型沒指明 → 用分數挑
        scores = {"resume": critique.resume_score, "cover_letter": critique.cover_letter_score,
                  "interview": critique.interview_score}
        docs = [d for d, s in scores.items() if s < _DOC_PASS]
    return SupervisorDecision(next_action="revise", docs_to_revise=docs,
                              rationale="（門檻備援）未達標需重寫")


def supervise_after_match(match: MatchReport, job: ParsedJob, profile: Profile) -> SupervisorDecision:
    """匹配後的調度決策（deep 分層）；LLM 失敗 → 門檻備援。"""
    try:
        llm = get_llm("deep").with_structured_output(SupervisorDecision)
        human = (f"【匹配報告】\n{match.model_dump_json(indent=2)}\n\n"
                 f"【職缺】\n{job.title} ＠ {job.company}")
        d = llm.invoke([("system", SUP_MATCH_SYSTEM), ("human", human)])
        if d.next_action not in ("proceed", "stop"):
            return _match_fallback(match)
        return d
    except Exception:
        return _match_fallback(match)


def supervise_after_critic(critique: CritiqueReport, revision_count: int,
                           max_revisions: int) -> SupervisorDecision:
    """品管後的調度決策（deep 分層）。達重寫上限一律 approve（硬保底，不信任 LLM 無限重寫）。"""
    if revision_count >= max_revisions:
        return SupervisorDecision(next_action="approve", rationale="已達重寫上限，送人工核可")
    try:
        llm = get_llm("deep").with_structured_output(SupervisorDecision)
        human = (f"【品管評審】\n{critique.model_dump_json(indent=2)}\n\n"
                 f"已重寫次數：{revision_count}／上限 {max_revisions}")
        d = llm.invoke([("system", SUP_CRITIC_SYSTEM), ("human", human)])
        if d.next_action not in ("approve", "revise"):
            return _critic_fallback(critique)
        if d.next_action == "revise":
            d.docs_to_revise = [x for x in d.docs_to_revise if x in _ALL_DOCS]
            if not d.docs_to_revise:  # revise 但沒指明任何有效文件 → 退回備援，避免空轉重寫
                return _critic_fallback(critique)
        return d
    except Exception:
        return _critic_fallback(critique)
