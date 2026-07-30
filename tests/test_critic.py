import pytest

from app.agents import critic as critic_mod
from app.models import (
    CoverLetter,
    CritiqueReport,
    InterviewKit,
    ParsedJob,
    TailoredResume,
)
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


def test_critique_package_only_reviews_selected_artifacts(monkeypatch):
    seen = {}
    canned = CritiqueReport(
        resume_score=80,
        cover_letter_score=10,
        interview_score=20,
        overall_pass=True,
        per_doc={"resume": ["補量化成果"], "cover_letter": ["不應出現"]},
    )

    class CaptureLLM:
        def with_structured_output(self, schema):
            return self

        def invoke(self, messages):
            seen["prompt"] = messages[-1][1]
            return canned

    monkeypatch.setattr(critic_mod, "get_llm", lambda tier: CaptureLLM())
    job, resume, _, _ = _artifacts()
    report = critic_mod.critique_package(job, resume=resume)

    assert "【客製履歷】" in seen["prompt"]
    assert "【求職信】" not in seen["prompt"] and "【面試準備】" not in seen["prompt"]
    assert report.cover_letter_score == 100 and report.interview_score == 100
    assert report.per_doc == {"resume": ["補量化成果"]}
    assert report.feedback == ["[履歷] 補量化成果"]


def test_critique_package_requires_at_least_one_artifact():
    job, _, _, _ = _artifacts()
    with pytest.raises(ValueError, match="沒有可供"):
        critic_mod.critique_package(job)
