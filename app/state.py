"""LangGraph 共享狀態。"""
from typing import TypedDict

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
