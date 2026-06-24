"""LangGraph 共享狀態。"""
import operator
from typing import Annotated, TypedDict

from app.models import (
    Profile, ParsedJob, MatchReport,
    CompanyBrief, TailoredResume, CoverLetter, InterviewKit, CritiqueReport,
)


class CopilotState(TypedDict):
    jd_text: str
    profile: Profile
    parsed_job: ParsedJob | None
    match_report: MatchReport | None
    company_brief: CompanyBrief | None
    tailored_resume: TailoredResume | None
    cover_letter: CoverLetter | None
    interview_kit: InterviewKit | None
    critique: CritiqueReport | None
    revision_count: int
    approved: bool | None
    # 優雅降級：任一節點 agent 失敗時附加 {node, message}，不中斷整條流程。
    # 用 operator.add 當 reducer，平行生成節點同時失敗也不會互蓋。
    errors: Annotated[list[dict], operator.add]
    # 逐節點 telemetry：{node, latency_ms, calls, input_tokens, output_tokens, cost_usd}。
    telemetry: Annotated[list[dict], operator.add]
