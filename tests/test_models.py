import pytest
from pydantic import ValidationError

from app.models import Profile, ParsedJob, MatchReport


def test_profile_minimal_valid():
    p = Profile(name="小明", summary="後端工程師", raw_text="...")
    assert p.skills == []            # 預設空清單
    assert p.years_experience is None


def test_parsed_job_requires_title_and_company():
    with pytest.raises(ValidationError):
        ParsedJob(title="AI 工程師")  # 缺 company


def test_match_report_score_must_be_in_range():
    ok = MatchReport(score=80, recommend_proceed=True, reason="符合度高")
    assert ok.score == 80
    with pytest.raises(ValidationError):
        MatchReport(score=120, recommend_proceed=True, reason="超出範圍")


def test_demo_profile_fixture_loads(demo_profile):
    assert demo_profile.name == "陳小安"
    assert "Python" in demo_profile.skills


def test_match_report_score_lower_bound():
    assert MatchReport(score=0, recommend_proceed=False, reason="完全不符").score == 0
    with pytest.raises(ValidationError):
        MatchReport(score=-1, recommend_proceed=False, reason="負分非法")


from app.models import CompanyBrief, TailoredResume, CoverLetter, InterviewKit


def test_company_brief_minimal_and_defaults():
    c = CompanyBrief(company="未來智能")
    assert c.data_limited is False
    assert c.benefits == [] and c.red_flags == [] and c.sources == []


def test_tailored_resume_requires_summary():
    r = TailoredResume(summary="針對 AI 工程師的定位", bullets=["做過 RAG"])
    assert r.ats_keywords_hit == []


def test_cover_letter_requires_body():
    cl = CoverLetter(body="敬啟者……")
    assert cl.company_facts_used == []


def test_interview_kit_defaults_empty_lists():
    k = InterviewKit()
    assert k.technical_questions == [] and k.reverse_questions == []


from app.models import CritiqueReport


def test_critique_report_defaults():
    c = CritiqueReport(resume_score=80, cover_letter_score=75, interview_score=70, overall_pass=True)
    assert c.feedback == []


def test_critique_report_score_bounds():
    import pytest
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        CritiqueReport(resume_score=101, cover_letter_score=0, interview_score=0, overall_pass=False)
