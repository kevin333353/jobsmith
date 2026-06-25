import pytest
from pydantic import ValidationError

from app.models import Profile, ParsedJob, MatchReport


def test_profile_minimal_valid():
    p = Profile(name="小明", summary="後端工程師", raw_text="...")
    assert p.skills == []            # 預設空清單
    assert p.years_experience is None


def test_profile_tolerates_model_output_variance():
    # 不同後端（codex/gpt）解析履歷時，name 常回 null、education 回陣列、字串欄位回 null、
    # list 欄位回單一字串、years 回「約 5 年」這種字串——schema 要收斂而非結構化解析失敗。
    p = Profile(
        name=None,
        summary=None,
        skills=None,
        experiences="單一字串經歷",
        education=["台大資工", "交大電機"],
        years_experience="約 5 年",
        raw_text=None,
    )
    assert p.name == "" and p.summary == "" and p.raw_text == ""
    assert p.skills == []
    assert p.experiences == ["單一字串經歷"]
    assert p.education == "台大資工、交大電機"
    assert p.years_experience == 5.0


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


from app.models import ResumeIssue, ResumeRewrite, ResumeAssessment


def test_resume_assessment_round_trips():
    a = ResumeAssessment(
        overall_score=78, clarity_score=80, impact_score=70,
        ats_keyword_score=75, localization_score=85, completeness_score=80,
        summary="整體不錯，量化成果可再加強。",
        strengths=["技術棧清楚"],
        issues=[ResumeIssue(severity="medium", area="工作經歷",
                            problem="缺乏量化", fix="加入數字，如『提升 30% 效能』")],
        rewrite_examples=[ResumeRewrite(original="負責後端開發",
                                        improved="主導後端 API 開發，支撐日活 5 萬",
                                        why="加入範圍與量化成果")],
    )
    dumped = a.model_dump()
    assert dumped["overall_score"] == 78
    assert dumped["issues"][0]["severity"] == "medium"
    assert dumped["rewrite_examples"][0]["improved"].startswith("主導")


def test_resume_assessment_score_bounds():
    with pytest.raises(ValidationError):
        ResumeAssessment(
            overall_score=120, clarity_score=0, impact_score=0,
            ats_keyword_score=0, localization_score=0, completeness_score=0,
            summary="x",
        )
