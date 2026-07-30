"""漸進式投遞包圖：解析與匹配後，只產生使用者勾選的文件。

公司情報與 AI 品管都是選配；品管只提供一次建議，不再自動重寫文件。這讓預設的
「快速投遞」只需解析、匹配、客製履歷三次模型呼叫，也保留完整投遞包的選擇。
human_gate 用 interrupt()，故 CLI 圖以 SqliteSaver checkpointer compile，執行需帶 thread_id。
"""
import os
import sqlite3
import time
from pathlib import Path

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from app import task_control, telemetry
from app.agents.company import research_company
from app.agents.cover_letter import write_cover_letter
from app.agents.critic import critique_package
from app.agents.interview import prepare_interview
from app.agents.match import match_profile
from app.agents.parse import parse_job
from app.agents.resume import tailor_resume
from app.models import (
    CompanyBrief,
    CoverLetter,
    CritiqueReport,
    InterviewKit,
    MatchReport,
    ParsedJob,
    SupervisorDecision,
    TailoredResume,
)
from app.state import CopilotState

_ALL_DOCS = {"resume", "cover_letter", "interview"}


def _safe(state: CopilotState, node: str, key: str, fn, fallback):
    """執行 agent；記錄延遲/token/成本 telemetry；失敗時回降級 artifact + error，不炸整條圖。

    用 begin_node/end_node 在「本節點自身的 context」開蒐集器：跨 SSE threadpool 邊界仍有效，
    且平行生成節點各自隔離（不互相灌 token）。
    """
    token = telemetry.begin_node()
    t0 = time.perf_counter()
    try:
        try:
            out = {key: fn()}
        except task_control.TaskCancelled:
            raise
        except Exception as exc:  # noqa: BLE001 — 任何 agent 例外都要優雅降級
            out = {key: fallback, "errors": [{"node": node, "message": str(exc)[:200]}]}
    finally:
        usage = telemetry.end_node(token)
    out["telemetry"] = [{"node": node,
                         "latency_ms": int((time.perf_counter() - t0) * 1000),
                         **usage}]
    return out


def parse_node(state: CopilotState) -> dict:
    if state.get("parsed_job") is not None:
        return {}  # 從職缺搜尋帶入已解析資料時直接重用，省一次模型呼叫
    return _safe(
        state, "parse", "parsed_job",
        lambda: parse_job(state["jd_text"]),
        ParsedJob(title="（解析失敗）", company="（未知）"),
    )


def match_node(state: CopilotState) -> dict:
    if state.get("match_report") is not None:
        return {}  # 從職缺搜尋帶入既有 AI 配對結果時直接重用
    return _safe(
        state, "match", "match_report",
        lambda: match_profile(state["parsed_job"], state["profile"]),
        MatchReport(score=0, recommend_proceed=False, reason="匹配評分失敗，已略過後續產出"),
    )


def company_research_node(state: CopilotState) -> dict:
    if not state.get("company_research_requested", True):
        return {}
    if state.get("company_brief") is not None:
        return {}
    return _safe(
        state, "company_research", "company_brief",
        lambda: research_company(state["parsed_job"].company),
        CompanyBrief(company=state["parsed_job"].company, data_limited=True,
                     note="公司情報查詢失敗"),
    )


def _targets(state: CopilotState) -> set[str]:
    """本次要產生的文件；未帶欄位代表舊版 checkpoint，維持「全部產出」相容性。"""
    requested = state.get("artifact_targets")
    if requested is None:
        return set(_ALL_DOCS)
    return {doc for doc in requested if doc in _ALL_DOCS}


def supervisor_match_node(state: CopilotState) -> dict:
    """以既有配對分數做本機門檻判斷，不再為單一布林路由額外呼叫一次 LLM。"""
    match = state["match_report"]
    proceed = bool(match and match.recommend_proceed and match.score >= 60)
    return {
        "supervisor_decision": SupervisorDecision(
            next_action="proceed" if proceed else "stop",
            rationale="配對分數達 60 且建議繼續" if proceed else "配對分數或建議未達產出門檻",
        )
    }


def resume_tailor_node(state: CopilotState) -> dict:
    if "resume" not in _targets(state):
        return {}
    return _safe(
        state, "resume_tailor", "tailored_resume",
        lambda: tailor_resume(state["parsed_job"], state["profile"], None),
        TailoredResume(summary="（履歷生成失敗，請重試）", notes="生成失敗"),
    )


def cover_letter_node(state: CopilotState) -> dict:
    if "cover_letter" not in _targets(state):
        return {}
    return _safe(
        state, "cover_letter", "cover_letter",
        lambda: write_cover_letter(
            state["parsed_job"], state["profile"], state.get("company_brief"),
            None),
        CoverLetter(body="（求職信生成失敗，請重試）"),
    )


def interview_prep_node(state: CopilotState) -> dict:
    if "interview" not in _targets(state):
        return {}
    return _safe(
        state, "interview_prep", "interview_kit",
        lambda: prepare_interview(
            state["parsed_job"], state["profile"], state.get("company_brief"),
            None),
        InterviewKit(cautions=["面試準備生成失敗，請重試"]),
    )


def join_node(state: CopilotState) -> dict:
    return {}


def critic_node(state: CopilotState) -> dict:
    targets = _targets(state)
    fallback_scores = {
        "resume_score": 0 if "resume" in targets else 100,
        "cover_letter_score": 0 if "cover_letter" in targets else 100,
        "interview_score": 0 if "interview" in targets else 100,
    }
    out = _safe(
        state, "critic", "critique",
        lambda: critique_package(
            state["parsed_job"], state.get("tailored_resume"),
            state.get("cover_letter"), state.get("interview_kit")),
        # 品管失敗仍保留成品並交給人看；不觸發任何自動重寫。
        CritiqueReport(**fallback_scores, overall_pass=True,
                       feedback=["AI 品管失敗，請直接人工檢視成品"]),
    )
    out["revision_count"] = 1
    return out


def human_gate_node(state: CopilotState) -> dict:
    # 批次模式：略過互動核可關卡，直接跑到底並以「待審」存檔；
    # 使用者事後到「我的投遞包」逐一核可或刪除，不必逐一卡在核可關卡。
    if state.get("batch"):
        return {"approved": None}
    critique = state.get("critique")
    decision = interrupt({
        "message": "請審閱投遞包並決定是否核可",
        "match_score": state["match_report"].score,
        "critique_pass": critique.overall_pass if critique else None,
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


def route_after_generation(state: CopilotState) -> str:
    """只有使用者明確勾選 AI 品管時才多花一次模型呼叫。"""
    return "critic" if state.get("quality_review", True) else "human_gate"


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
    """編譯漸進式產出圖。checkpointer 預設用 SqliteSaver；測試可注入 MemorySaver。"""
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
    g.add_conditional_edges(
        "join", route_after_generation,
        {"critic": "critic", "human_gate": "human_gate"},
    )
    g.add_edge("critic", "human_gate")
    g.add_edge("human_gate", END)
    return g.compile(checkpointer=checkpointer or _sqlite_checkpointer())
