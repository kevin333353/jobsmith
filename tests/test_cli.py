from app.models import (
    ParsedJob, MatchReport, CompanyBrief, TailoredResume, CoverLetter,
    InterviewKit, CritiqueReport,
)
from app import cli as cli_mod
from app import graph as graph_mod


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
        "critique": CritiqueReport(resume_score=88, cover_letter_score=85,
                                   interview_score=82, overall_pass=True),
        "revision_count": 1,
        "approved": True,
    }


def test_format_output_includes_critique_and_approval():
    text = cli_mod.format_output(_full_state(), job_title="AI 工程師")
    assert "88" in text
    assert "核可" in text
    assert "客製定位" in text


def test_format_output_handles_stop_path():
    state = {
        "parsed_job": ParsedJob(title="X", company="Y"),
        "match_report": MatchReport(score=30, recommend_proceed=False, reason="不符"),
        "company_brief": None, "tailored_resume": None, "cover_letter": None,
        "interview_kit": None, "critique": None, "revision_count": 0, "approved": None,
    }
    text = cli_mod.format_output(state, job_title="X")
    assert "30" in text


def _patch_graph_agents(monkeypatch):
    monkeypatch.setattr(graph_mod, "parse_job",
                        lambda jd_text: ParsedJob(title="AI 工程師", company="未來智能"))
    monkeypatch.setattr(graph_mod, "match_profile",
                        lambda job, profile: MatchReport(score=82, recommend_proceed=True, reason="吻合"))
    monkeypatch.setattr(graph_mod, "research_company",
                        lambda name: CompanyBrief(company=name))
    monkeypatch.setattr(graph_mod, "tailor_resume",
                        lambda job, profile, feedback=None: TailoredResume(summary="履歷"))
    monkeypatch.setattr(graph_mod, "write_cover_letter",
                        lambda job, profile, company, feedback=None: CoverLetter(body="信"))
    monkeypatch.setattr(graph_mod, "prepare_interview",
                        lambda job, profile, company, feedback=None: InterviewKit())
    monkeypatch.setattr(graph_mod, "critique_package",
                        lambda job, r, c, k: CritiqueReport(resume_score=90, cover_letter_score=90,
                                                            interview_score=90, overall_pass=True))


def test_run_handles_interrupt_and_resume(monkeypatch, tmp_path):
    jd_file = tmp_path / "jd.txt"
    jd_file.write_text("一些 JD", encoding="utf-8")
    _patch_graph_agents(monkeypatch)
    monkeypatch.setattr("builtins.input", lambda *a, **k: "y")

    result = cli_mod.run(str(jd_file))
    assert result["approved"] is True
    assert result["tailored_resume"].summary == "履歷"


def test_run_stop_path_no_prompt(monkeypatch, tmp_path):
    jd_file = tmp_path / "jd.txt"
    jd_file.write_text("一些 JD", encoding="utf-8")
    _patch_graph_agents(monkeypatch)
    monkeypatch.setattr(graph_mod, "match_profile",
                        lambda job, profile: MatchReport(score=30, recommend_proceed=False, reason="不符"))

    def no_input(*a, **k):
        raise AssertionError("stop 路徑不應該詢問核可")
    monkeypatch.setattr("builtins.input", no_input)

    result = cli_mod.run(str(jd_file))
    assert result["tailored_resume"] is None
