"""Supervisor 反思迴圈圖：parse → match →（proceed）company_research → 三生成並行
→ join → critic →（revise 回圈 / approve）→ human_gate(interrupt) → END。

迴圈採單節點回圈（critic→company_research）；company_research 重寫時跳過搜尋；
生成節點讀 state 的 critique.feedback 改進；重寫覆寫各自 state key（last-write-wins，不需 reducer）。
human_gate 用 interrupt()，故圖以 SqliteSaver checkpointer compile，執行需帶 thread_id。
"""
import os
import sqlite3
import time
from pathlib import Path

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import interrupt

from app import telemetry
from app.state import CopilotState
from app.agents.parse import parse_job
from app.agents.match import match_profile
from app.agents.company import research_company
from app.agents.resume import tailor_resume
from app.agents.cover_letter import write_cover_letter
from app.agents.interview import prepare_interview
from app.agents.critic import critique_package
from app.agents.supervisor import supervise_after_match, supervise_after_critic

from app.models import (
    ParsedJob, MatchReport, CompanyBrief, TailoredResume, CoverLetter, InterviewKit,
    CritiqueReport, SupervisorDecision,
)

MAX_REVISIONS = 3  # 最多評審次數（至多 2 次重寫），防無限迴圈
_DOC_PASS = 75     # 安全網：per_doc 未指明時，分數低於此者視為需重寫
_ALL_DOCS = {"resume", "cover_letter", "interview"}


def _safe(state: CopilotState, node: str, key: str, fn, fallback):
    """執行 agent；記錄延遲/token/成本 telemetry；失敗時回降級 artifact + error，不炸整條圖。

    用 begin_node/end_node 在「本節點自身的 context」開蒐集器：跨 SSE threadpool 邊界仍有效，
    且平行生成節點各自隔離（不互相灌 token）。
    """
    token = telemetry.begin_node()
    t0 = time.perf_counter()
    try:
        out = {key: fn()}
    except Exception as exc:  # noqa: BLE001 — 任何 agent 例外都要優雅降級
        out = {key: fallback, "errors": [{"node": node, "message": str(exc)[:200]}]}
    usage = telemetry.end_node(token)
    out["telemetry"] = [{"node": node,
                         "latency_ms": int((time.perf_counter() - t0) * 1000),
                         **usage}]
    return out


def parse_node(state: CopilotState) -> dict:
    return _safe(
        state, "parse", "parsed_job",
        lambda: parse_job(state["jd_text"]),
        ParsedJob(title="（解析失敗）", company="（未知）"),
    )


def match_node(state: CopilotState) -> dict:
    return _safe(
        state, "match", "match_report",
        lambda: match_profile(state["parsed_job"], state["profile"]),
        MatchReport(score=0, recommend_proceed=False, reason="匹配評分失敗，已略過後續產出"),
    )


def company_research_node(state: CopilotState) -> dict:
    if state.get("company_brief") is not None:
        return {}  # 重寫回圈時不重複搜尋
    return _safe(
        state, "company_research", "company_brief",
        lambda: research_company(state["parsed_job"].company),
        CompanyBrief(company=state["parsed_job"].company, data_limited=True,
                     note="公司情報查詢失敗"),
    )


def _feedback(state: CopilotState, doc: str):
    """該文件這一輪的專屬品管回饋（無則 None）。"""
    critique = state.get("critique")
    if not critique:
        return None
    return critique.per_doc.get(doc) or None


def _targets(state: CopilotState) -> set[str]:
    """這一輪要(重)寫哪些文件：首輪（無 critique）全部；重寫輪依 supervisor / per_doc / 分數。"""
    critique = state.get("critique")
    if critique is None:
        return set(_ALL_DOCS)
    decision = state.get("supervisor_decision")  # supervisor 指定優先
    if decision and decision.docs_to_revise:
        return {d for d in decision.docs_to_revise if d in _ALL_DOCS}
    docs = {d for d in (critique.per_doc or {}) if d in _ALL_DOCS}
    if not docs and not critique.overall_pass:  # 安全網：模型沒指明就用分數挑
        if critique.resume_score < _DOC_PASS:
            docs.add("resume")
        if critique.cover_letter_score < _DOC_PASS:
            docs.add("cover_letter")
        if critique.interview_score < _DOC_PASS:
            docs.add("interview")
    return docs


def supervisor_match_node(state: CopilotState) -> dict:
    """① Supervisor：看匹配報告動態決定 proceed / stop（telemetry 經 _safe 記錄）。"""
    return _safe(
        state, "supervisor_match", "supervisor_decision",
        lambda: supervise_after_match(
            state["match_report"], state["parsed_job"], state["profile"]),
        SupervisorDecision(next_action="stop", rationale="supervisor 失敗，保守停止"),
    )


def supervisor_critic_node(state: CopilotState) -> dict:
    """① Supervisor：看品管評審動態決定 approve / revise + docs_to_revise。"""
    return _safe(
        state, "supervisor_critic", "supervisor_decision",
        lambda: supervise_after_critic(
            state["critique"], state.get("revision_count", 0), MAX_REVISIONS),
        SupervisorDecision(next_action="approve", rationale="supervisor 失敗，直接送核可"),
    )


def resume_tailor_node(state: CopilotState) -> dict:
    if "resume" not in _targets(state):
        return {}  # 重寫輪此文件已達標 → 保留現有、不重跑
    return _safe(
        state, "resume_tailor", "tailored_resume",
        lambda: tailor_resume(state["parsed_job"], state["profile"], _feedback(state, "resume")),
        TailoredResume(summary="（履歷生成失敗，請重試）", notes="生成失敗"),
    )


def cover_letter_node(state: CopilotState) -> dict:
    if "cover_letter" not in _targets(state):
        return {}
    return _safe(
        state, "cover_letter", "cover_letter",
        lambda: write_cover_letter(
            state["parsed_job"], state["profile"], state.get("company_brief"),
            _feedback(state, "cover_letter")),
        CoverLetter(body="（求職信生成失敗，請重試）"),
    )


def interview_prep_node(state: CopilotState) -> dict:
    if "interview" not in _targets(state):
        return {}
    return _safe(
        state, "interview_prep", "interview_kit",
        lambda: prepare_interview(
            state["parsed_job"], state["profile"], state.get("company_brief"),
            _feedback(state, "interview")),
        InterviewKit(cautions=["面試準備生成失敗，請重試"]),
    )


def join_node(state: CopilotState) -> dict:
    return {}


def critic_node(state: CopilotState) -> dict:
    out = _safe(
        state, "critic", "critique",
        lambda: critique_package(
            state["parsed_job"], state["tailored_resume"],
            state["cover_letter"], state["interview_kit"]),
        # 評審失敗則放行到人工關卡（overall_pass=True 避免無謂重寫），由人決定。
        CritiqueReport(resume_score=0, cover_letter_score=0, interview_score=0,
                       overall_pass=True, feedback=["品管評審失敗，請人工檢視"]),
    )
    out["revision_count"] = state.get("revision_count", 0) + 1
    return out


def human_gate_node(state: CopilotState) -> dict:
    # 批次模式：略過互動核可關卡，直接跑到底並以「待審」存檔；
    # 使用者事後到「我的投遞包」逐一核可或刪除，不必逐一卡在核可關卡。
    if state.get("batch"):
        return {"approved": None}
    decision = interrupt({
        "message": "請審閱投遞包並決定是否核可",
        "match_score": state["match_report"].score,
        "critique_pass": state["critique"].overall_pass,
    })
    approved = str(decision).strip().lower() in ("y", "yes", "approve", "是", "核可")
    return {"approved": approved}


def route_match_decision(state: CopilotState) -> str:
    """依 supervisor 決策路由；match agent 崩潰則強制續做（避免誤判為低適配而停止）。"""
    match_errored = any(e.get("node") == "match" for e in (state.get("errors") or []))
    if match_errored:
        return "company_research"
    decision = state.get("supervisor_decision")
    return "company_research" if decision and decision.next_action == "proceed" else "stop"


def route_critic_decision(state: CopilotState) -> str:
    """依 supervisor 決策路由 revise / approve（上限保底已在 supervise_after_critic 處理）。

    防呆：revise 但實際算不出要重寫哪份文件（_targets 空）→ 視為 approve，避免空轉重寫。
    """
    decision = state.get("supervisor_decision")
    if decision and decision.next_action == "revise" and _targets(state):
        return "revise"
    return "approve"


def _default_db_path() -> str:
    """checkpoint db 路徑；COPILOT_DB 可覆寫（測試設 :memory: 以隔離）。"""
    return os.environ.get(
        "COPILOT_DB", str(Path(__file__).parent.parent / "data" / "checkpoints.sqlite"))


def _sqlite_checkpointer() -> SqliteSaver:
    """檔案型 checkpointer：跨程序重啟仍能 resume 同一 thread_id（人工核可關卡）。

    check_same_thread=False 供 FastAPI threadpool 多執行緒共用單一連線（單人本機足夠）。
    """
    conn = sqlite3.connect(_default_db_path(), check_same_thread=False)
    saver = SqliteSaver(conn)
    saver.setup()
    return saver


def build_graph(checkpointer=None):
    """編譯反思迴圈圖。checkpointer 預設用 SqliteSaver（持久化）；測試可注入 MemorySaver。"""
    g = StateGraph(CopilotState)
    g.add_node("parse", parse_node)
    g.add_node("match", match_node)
    g.add_node("supervisor_match", supervisor_match_node)
    g.add_node("company_research", company_research_node)
    g.add_node("resume_tailor", resume_tailor_node)
    g.add_node("cover_letter", cover_letter_node)
    g.add_node("interview_prep", interview_prep_node)
    g.add_node("join", join_node)
    g.add_node("critic", critic_node)
    g.add_node("supervisor_critic", supervisor_critic_node)
    g.add_node("human_gate", human_gate_node)

    g.add_edge(START, "parse")
    g.add_edge("parse", "match")
    g.add_edge("match", "supervisor_match")
    g.add_conditional_edges(
        "supervisor_match", route_match_decision,
        {"company_research": "company_research", "stop": END},
    )
    g.add_edge("company_research", "resume_tailor")
    g.add_edge("company_research", "cover_letter")
    g.add_edge("company_research", "interview_prep")
    g.add_edge("resume_tailor", "join")
    g.add_edge("cover_letter", "join")
    g.add_edge("interview_prep", "join")
    g.add_edge("join", "critic")
    g.add_edge("critic", "supervisor_critic")
    g.add_conditional_edges(
        "supervisor_critic", route_critic_decision,
        {"revise": "company_research", "approve": "human_gate"},
    )
    g.add_edge("human_gate", END)
    return g.compile(checkpointer=checkpointer or _sqlite_checkpointer())
