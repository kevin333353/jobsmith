"""LangGraph 共享狀態。"""
import operator
from typing import Annotated, TypedDict

from app.models import (
    CompanyBrief,
    CoverLetter,
    CritiqueReport,
    InterviewKit,
    MatchReport,
    ParsedJob,
    Profile,
    SupervisorDecision,
    TailoredResume,
)


class CopilotState(TypedDict):
    jd_text: str
    profile: Profile
    # 本次實際要產出的文件；舊 checkpoint 未帶此欄位時 graph 會相容為全部產出。
    artifact_targets: list[str]
    # 公司情報與 AI 品管都是選配，避免每次都支付固定的額外呼叫成本。
    company_research_requested: bool
    quality_review: bool
    parsed_job: ParsedJob | None
    match_report: MatchReport | None
    supervisor_decision: SupervisorDecision | None
    company_brief: CompanyBrief | None
    tailored_resume: TailoredResume | None
    cover_letter: CoverLetter | None
    interview_kit: InterviewKit | None
    critique: CritiqueReport | None
    revision_count: int
    approved: bool | None
    # 批次模式：清單逐一無人值守產生投遞包時為 True，human_gate 略過互動核可、
    # 直接跑到底並以「待審」存檔，使用者事後到「我的投遞包」核可/刪除。
    batch: bool
    # 優雅降級：任一節點 agent 失敗時附加 {node, message}，不中斷整條流程。
    # 用 operator.add 當 reducer，平行生成節點同時失敗也不會互蓋。
    errors: Annotated[list[dict], operator.add]
    # 逐節點 telemetry：{node, latency_ms, calls, input_tokens, output_tokens, cost_usd}。
    telemetry: Annotated[list[dict], operator.add]
