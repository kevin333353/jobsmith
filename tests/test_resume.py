from app.models import TailoredResume
from app.agents import resume as resume_mod
from tests.conftest import FakeLLM


def test_tailor_resume_returns_tailored_resume(monkeypatch, demo_profile, sample_parsed_job):
    canned = TailoredResume(
        summary="三年後端 + 一年 LLM，貼合此 AI 工程師職缺",
        bullets=["用 LangChain 建 RAG 客服，工單降 25%"],
        ats_keywords_hit=["Python", "LangChain"],
        ats_keywords_missing=["LangGraph"],
    )
    monkeypatch.setattr(resume_mod, "get_llm", lambda tier: FakeLLM(canned))

    result = resume_mod.tailor_resume(sample_parsed_job, demo_profile)

    assert isinstance(result, TailoredResume)
    assert "Python" in result.ats_keywords_hit


def test_tailor_resume_uses_standard_tier(monkeypatch, demo_profile, sample_parsed_job):
    seen = {}
    canned = TailoredResume(summary="x")

    def fake_get_llm(tier):
        seen["tier"] = tier
        return FakeLLM(canned)

    monkeypatch.setattr(resume_mod, "get_llm", fake_get_llm)
    resume_mod.tailor_resume(sample_parsed_job, demo_profile)
    assert seen["tier"] == "standard"
