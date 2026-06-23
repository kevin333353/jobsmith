from app.models import Profile, ResumeAssessment, ResumeIssue
from app.agents import resume_eval as mod
from tests.conftest import FakeLLM


def test_structure_profile_returns_profile(monkeypatch):
    canned = Profile(name="王小明", summary="後端工程師", skills=["Python"], raw_text="原文")
    monkeypatch.setattr(mod, "get_llm", lambda tier: FakeLLM(canned))
    result = mod.structure_profile("（履歷全文）")
    assert isinstance(result, Profile)
    assert result.name == "王小明"


def test_structure_profile_uses_cheap_tier(monkeypatch):
    seen = {}
    canned = Profile(name="x", summary="y", raw_text="z")

    def fake(tier):
        seen["tier"] = tier
        return FakeLLM(canned)

    monkeypatch.setattr(mod, "get_llm", fake)
    mod.structure_profile("text")
    assert seen["tier"] == "cheap"


def test_structure_profile_fills_raw_text_when_empty(monkeypatch):
    canned = Profile(name="王", summary="s", raw_text="")
    monkeypatch.setattr(mod, "get_llm", lambda tier: FakeLLM(canned))
    result = mod.structure_profile("完整履歷文字")
    assert result.raw_text == "完整履歷文字"


def test_evaluate_resume_returns_assessment(monkeypatch):
    canned = ResumeAssessment(
        overall_score=78, clarity_score=80, impact_score=70,
        ats_keyword_score=75, localization_score=85, completeness_score=80,
        summary="整體不錯", strengths=["技能清楚"],
        issues=[ResumeIssue(severity="medium", area="工作經歷", problem="缺量化", fix="加數字")],
    )
    monkeypatch.setattr(mod, "get_llm", lambda tier, **kw: FakeLLM(canned))
    result = mod.evaluate_resume("履歷全文", Profile(name="王", summary="s", raw_text="r"))
    assert isinstance(result, ResumeAssessment)
    assert result.overall_score == 78
    assert result.issues[0].severity == "medium"


def test_evaluate_resume_uses_deep_tier_with_larger_max_tokens(monkeypatch):
    seen = {}
    canned = ResumeAssessment(
        overall_score=1, clarity_score=1, impact_score=1, ats_keyword_score=1,
        localization_score=1, completeness_score=1, summary="x",
    )

    def fake(tier, **kw):
        seen["tier"] = tier
        seen["kw"] = kw
        return FakeLLM(canned)

    monkeypatch.setattr(mod, "get_llm", fake)
    mod.evaluate_resume("t", Profile(name="a", summary="b", raw_text="c"))
    assert seen["tier"] == "deep"
    # 健檢輸出大且 deep 為推理模型，max_tokens 必須高於預設 2000，避免截斷
    assert seen["kw"].get("max_tokens", 0) > 2000
