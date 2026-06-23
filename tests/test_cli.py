from app.models import (
    ParsedJob, MatchReport, CompanyBrief, TailoredResume, CoverLetter, InterviewKit,
)
from app import cli as cli_mod


def test_load_profile_reads_demo():
    p = cli_mod.load_profile("data/demo_profile.json")
    assert p.name == "陳小安"


def _full_state():
    return {
        "parsed_job": ParsedJob(title="AI 工程師", company="未來智能"),
        "match_report": MatchReport(score=82, matched=["Python"], gaps=["年資"],
                                    suggestions=["補強 X"], recommend_proceed=True, reason="吻合"),
        "company_brief": CompanyBrief(company="未來智能", salary_range="月薪 6 萬起",
                                      benefits=["彈性工時"], red_flags=["加班多"]),
        "tailored_resume": TailoredResume(summary="客製定位", bullets=["做過 RAG"],
                                          ats_keywords_hit=["Python"]),
        "cover_letter": CoverLetter(body="敬啟者……"),
        "interview_kit": InterviewKit(technical_questions=["解釋 RAG"],
                                      reverse_questions=["團隊架構？"]),
    }


def test_format_output_includes_all_sections():
    text = cli_mod.format_output(_full_state(), job_title="AI 工程師")
    assert "AI 工程師" in text
    assert "82" in text
    assert "月薪 6 萬起" in text
    assert "客製定位" in text
    assert "敬啟者" in text
    assert "解釋 RAG" in text


def test_format_output_handles_stop_path():
    state = {
        "parsed_job": ParsedJob(title="X", company="Y"),
        "match_report": MatchReport(score=30, recommend_proceed=False, reason="不符"),
        "company_brief": None, "tailored_resume": None,
        "cover_letter": None, "interview_kit": None,
    }
    text = cli_mod.format_output(state, job_title="X")
    assert "30" in text
    assert "不符" in text


def test_run_invokes_graph_and_returns_state(monkeypatch, tmp_path):
    jd_file = tmp_path / "jd.txt"
    jd_file.write_text("一些 JD", encoding="utf-8")
    fake_final = _full_state()

    class FakeGraph:
        def invoke(self, state):
            return fake_final

    monkeypatch.setattr(cli_mod, "build_graph", lambda: FakeGraph())

    result = cli_mod.run(str(jd_file))
    assert result["match_report"].score == 82
