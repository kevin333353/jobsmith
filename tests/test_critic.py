from app.models import (
    ParsedJob, TailoredResume, CoverLetter, InterviewKit, CritiqueReport,
)
from app.agents import critic as critic_mod
from tests.conftest import FakeLLM


def _artifacts():
    job = ParsedJob(title="AI 工程師", company="未來智能")
    resume = TailoredResume(summary="定位")
    cover = CoverLetter(body="敬啟者")
    kit = InterviewKit(technical_questions=["Q"])
    return job, resume, cover, kit


def test_critique_package_returns_report(monkeypatch):
    canned = CritiqueReport(resume_score=88, cover_letter_score=82, interview_score=80,
                            overall_pass=True, feedback=[])
    monkeypatch.setattr(critic_mod, "get_llm", lambda tier: FakeLLM(canned))

    report = critic_mod.critique_package(*_artifacts())

    assert isinstance(report, CritiqueReport)
    assert report.overall_pass is True


def test_critique_package_uses_deep_tier(monkeypatch):
    seen = {}
    canned = CritiqueReport(resume_score=50, cover_letter_score=50, interview_score=50,
                            overall_pass=False, feedback=["改具體一點"])

    def fake_get_llm(tier):
        seen["tier"] = tier
        return FakeLLM(canned)

    monkeypatch.setattr(critic_mod, "get_llm", fake_get_llm)
    critic_mod.critique_package(*_artifacts())
    assert seen["tier"] == "deep"
