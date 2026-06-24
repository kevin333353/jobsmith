"""Supervisor 反思迴圈圖：parse → match →（proceed）company_research → 三生成並行
→ join → critic →（revise 回圈 / approve）→ human_gate(interrupt) → END。

迴圈採單節點回圈（critic→company_research）；company_research 重寫時跳過搜尋；
生成節點讀 state 的 critique.feedback 改進；重寫覆寫各自 state key（last-write-wins，不需 reducer）。
human_gate 用 interrupt()，故圖以 MemorySaver checkpointer compile，執行需帶 thread_id。
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

from app.models import (
    ParsedJob, MatchReport, CompanyBrief, TailoredResume, CoverLetter, InterviewKit,
    CritiqueReport,
)

PROCEED_SCORE_THRESHOLD = 60
MAX_REVISIONS = 2  # 最多評審次數（至多 1 次重寫），防無限迴圈


def _safe(state: CopilotState, node: str, key: str, fn, fallback):
    """執行 agent；記錄延遲/token/成本 telemetry；失敗時回降級 artifact + error，不炸整條圖。"""
    mark = telemetry.marker()
    t0 = time.perf_counter()
    try:
        out = {key: fn()}
    except Exception as exc:  # noqa: BLE001 — 任何 agent 例外都要優雅降級
        out = {key: fallback, "errors": [{"node": node, "message": str(exc)[:200]}]}
    usage = telemetry.drain_since(mark)
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


def _feedback(state: CopilotState):
    critique = state.get("critique")
    return critique.feedback if critique else None


def resume_tailor_node(state: CopilotState) -> dict:
    return _safe(
        state, "resume_tailor", "tailored_resume",
        lambda: tailor_resume(state["parsed_job"], state["profile"], _feedback(state)),
        TailoredResume(summary="（履歷生成失敗，請重試）", notes="生成失敗"),
    )


def cover_letter_node(state: CopilotState) -> dict:
    return _safe(
        state, "cover_letter", "cover_letter",
        lambda: write_cover_letter(
            state["parsed_job"], state["profile"], state.get("company_brief"), _feedback(state)),
        CoverLetter(body="（求職信生成失敗，請重試）"),
    )


def interview_prep_node(state: CopilotState) -> dict:
    return _safe(
        state, "interview_prep", "interview_kit",
        lambda: prepare_interview(
            state["parsed_job"], state["profile"], state.get("company_brief"), _feedback(state)),
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
    decision = interrupt({
        "message": "請審閱投遞包並決定是否核可",
        "match_score": state["match_report"].score,
        "critique_pass": state["critique"].overall_pass,
    })
    approved = str(decision).strip().lower() in ("y", "yes", "approve", "是", "核可")
    return {"approved": approved}


def route_after_match(state: CopilotState) -> str:
    report = state["match_report"]
    # 若 match agent 失敗（已降級），不要把崩潰誤判為「低適配 → 停止」：照樣產出降級投遞包。
    match_errored = any(e.get("node") == "match" for e in (state.get("errors") or []))
    if match_errored or (report.recommend_proceed and report.score >= PROCEED_SCORE_THRESHOLD):
        return "company_research"
    return "stop"


def route_after_critic(state: CopilotState) -> str:
    critique = state["critique"]
    if critique.overall_pass or state.get("revision_count", 0) >= MAX_REVISIONS:
        return "approve"
    return "revise"


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
    g.add_node("company_research", company_research_node)
    g.add_node("resume_tailor", resume_tailor_node)
    g.add_node("cover_letter", cover_letter_node)
    g.add_node("interview_prep", interview_prep_node)
    g.add_node("join", join_node)
    g.add_node("critic", critic_node)
    g.add_node("human_gate", human_gate_node)

    g.add_edge(START, "parse")
    g.add_edge("parse", "match")
    g.add_conditional_edges(
        "match", route_after_match,
        {"company_research": "company_research", "stop": END},
    )
    g.add_edge("company_research", "resume_tailor")
    g.add_edge("company_research", "cover_letter")
    g.add_edge("company_research", "interview_prep")
    g.add_edge("resume_tailor", "join")
    g.add_edge("cover_letter", "join")
    g.add_edge("interview_prep", "join")
    g.add_edge("join", "critic")
    g.add_conditional_edges(
        "critic", route_after_critic,
        {"revise": "company_research", "approve": "human_gate"},
    )
    g.add_edge("human_gate", END)
    return g.compile(checkpointer=checkpointer or _sqlite_checkpointer())
