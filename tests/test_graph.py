import pytest
from langgraph.types import Command

from app import graph as graph_mod
from app.models import (
    CompanyBrief,
    CoverLetter,
    CritiqueReport,
    InterviewKit,
    MatchReport,
    ParsedJob,
    SupervisorDecision,
    TailoredResume,
)

CONFIG = {"configurable": {"thread_id": "test-thread"}}


def test_safe_does_not_swallow_task_cancellation():
    from app import task_control

    def cancelled():
        raise task_control.TaskCancelled("stop")

    with pytest.raises(task_control.TaskCancelled):
        graph_mod._safe({}, "parse", "parsed_job", cancelled, None)


def _patch_base(monkeypatch, report: MatchReport):
    monkeypatch.setattr(graph_mod, "parse_job",
                        lambda jd_text: ParsedJob(title="AI 工程師", company="未來智能"))
    monkeypatch.setattr(graph_mod, "match_profile", lambda job, profile: report)
    monkeypatch.setattr(graph_mod, "research_company",
                        lambda name: CompanyBrief(company=name, funding="B 輪"))
    monkeypatch.setattr(graph_mod, "tailor_resume",
                        lambda job, profile, feedback=None: TailoredResume(summary="履歷"))
    monkeypatch.setattr(graph_mod, "write_cover_letter",
                        lambda job, profile, company, feedback=None: CoverLetter(body="信"))
    monkeypatch.setattr(graph_mod, "prepare_interview",
                        lambda job, profile, company, feedback=None: InterviewKit(technical_questions=["Q"]))


def _passing_critic(monkeypatch):
    monkeypatch.setattr(graph_mod, "critique_package",
                        lambda job, r, c, k: CritiqueReport(
                            resume_score=90, cover_letter_score=88, interview_score=85,
                            overall_pass=True, feedback=[]))


def _initial(profile):
    return {
        "jd_text": "（任意）", "profile": profile,
        "artifact_targets": ["resume", "cover_letter", "interview"],
        "company_research_requested": True, "quality_review": True,
        "parsed_job": None, "match_report": None, "company_brief": None,
        "tailored_resume": None, "cover_letter": None, "interview_kit": None,
        "critique": None, "revision_count": 0, "approved": None,
    }


def test_proceed_runs_to_human_gate_then_resumes(monkeypatch, demo_profile):
    _patch_base(monkeypatch, MatchReport(score=82, recommend_proceed=True, reason="吻合"))
    _passing_critic(monkeypatch)
    g = graph_mod.build_graph()

    result = g.invoke(_initial(demo_profile), CONFIG)
    assert "__interrupt__" in result

    final = g.invoke(Command(resume="y"), CONFIG)
    assert final["approved"] is True
    assert final["tailored_resume"].summary == "履歷"
    assert final["company_brief"].funding == "B 輪"
    assert final["critique"].overall_pass is True


def test_stop_path_no_interrupt(monkeypatch, demo_profile):
    _patch_base(monkeypatch, MatchReport(score=40, recommend_proceed=False, reason="不符"))
    _passing_critic(monkeypatch)
    g = graph_mod.build_graph()

    result = g.invoke(_initial(demo_profile), CONFIG)
    assert "__interrupt__" not in result
    assert result["match_report"].score == 40
    assert result["tailored_resume"] is None


def test_failing_critic_runs_once_and_never_rewrites(monkeypatch, demo_profile):
    _patch_base(monkeypatch, MatchReport(score=82, recommend_proceed=True, reason="吻合"))
    calls = {"resume": 0, "critic": 0}

    def counting_resume(job, profile, feedback=None):
        calls["resume"] += 1
        return TailoredResume(summary=f"v{calls['resume']}")

    def always_fail(job, r, c, k):
        calls["critic"] += 1
        return CritiqueReport(resume_score=10, cover_letter_score=10, interview_score=10,
                              overall_pass=False)  # 無 per_doc → 安全網用分數挑全部

    monkeypatch.setattr(graph_mod, "tailor_resume", counting_resume)
    monkeypatch.setattr(graph_mod, "critique_package", always_fail)
    g = graph_mod.build_graph()

    result = g.invoke(_initial(demo_profile), CONFIG)
    assert calls["critic"] == 1
    assert calls["resume"] == 1
    assert result["revision_count"] == 1
    assert "__interrupt__" in result


def test_quick_mode_only_generates_resume(monkeypatch, demo_profile):
    _patch_base(monkeypatch, MatchReport(score=82, recommend_proceed=True, reason="吻合"))
    calls = {"company": 0, "resume": 0, "cover": 0, "interview": 0, "critic": 0}
    monkeypatch.setattr(
        graph_mod, "research_company",
        lambda name: calls.__setitem__("company", calls["company"] + 1),
    )
    monkeypatch.setattr(
        graph_mod, "tailor_resume",
        lambda job, profile, feedback=None: (
            calls.__setitem__("resume", calls["resume"] + 1) or TailoredResume(summary="r")
        ),
    )
    monkeypatch.setattr(
        graph_mod, "write_cover_letter",
        lambda *args, **kwargs: calls.__setitem__("cover", calls["cover"] + 1),
    )
    monkeypatch.setattr(
        graph_mod, "prepare_interview",
        lambda *args, **kwargs: calls.__setitem__("interview", calls["interview"] + 1),
    )
    monkeypatch.setattr(
        graph_mod, "critique_package",
        lambda *args, **kwargs: calls.__setitem__("critic", calls["critic"] + 1),
    )
    g = graph_mod.build_graph()
    initial = _initial(demo_profile)
    initial.update({
        "artifact_targets": ["resume"],
        "company_research_requested": False,
        "quality_review": False,
    })

    result = g.invoke(initial, CONFIG)
    assert "__interrupt__" in result
    assert calls == {"company": 0, "resume": 1, "cover": 0, "interview": 0, "critic": 0}
    assert result["cover_letter"] is None
    assert result["interview_kit"] is None
    assert result["critique"] is None


def test_selected_documents_and_optional_review_each_run_once(monkeypatch, demo_profile):
    _patch_base(monkeypatch, MatchReport(score=82, recommend_proceed=True, reason="吻合"))
    calls = {"resume": 0, "cover": 0, "interview": 0, "critic": 0}

    def cnt_cover(job, profile, company, feedback=None):
        calls["cover"] += 1
        return CoverLetter(body="c")

    def cnt_interview(job, profile, company, feedback=None):
        calls["interview"] += 1
        return InterviewKit()

    def review(job, resume, cover, interview):
        calls["critic"] += 1
        assert resume is None
        assert cover is not None and interview is not None
        return CritiqueReport(resume_score=100, cover_letter_score=90, interview_score=90,
                              overall_pass=True)

    monkeypatch.setattr(
        graph_mod, "tailor_resume",
        lambda *args, **kwargs: calls.__setitem__("resume", calls["resume"] + 1),
    )
    monkeypatch.setattr(graph_mod, "write_cover_letter", cnt_cover)
    monkeypatch.setattr(graph_mod, "prepare_interview", cnt_interview)
    monkeypatch.setattr(graph_mod, "critique_package", review)
    g = graph_mod.build_graph()
    initial = _initial(demo_profile)
    initial["artifact_targets"] = ["cover_letter", "interview"]

    g.invoke(initial, CONFIG)
    assert calls["resume"] == 0
    assert calls["cover"] == 1
    assert calls["interview"] == 1
    assert calls["critic"] == 1


def test_prefilled_job_and_match_skip_duplicate_agents(monkeypatch, demo_profile):
    _patch_base(monkeypatch, MatchReport(score=82, recommend_proceed=True, reason="吻合"))
    monkeypatch.setattr(
        graph_mod, "parse_job",
        lambda text: (_ for _ in ()).throw(AssertionError("parse should be reused")),
    )
    monkeypatch.setattr(
        graph_mod, "match_profile",
        lambda job, profile: (_ for _ in ()).throw(AssertionError("match should be reused")),
    )
    g = graph_mod.build_graph()
    initial = _initial(demo_profile)
    initial.update({
        "parsed_job": ParsedJob(title="已解析職缺", company="既有公司"),
        "match_report": MatchReport(score=85, recommend_proceed=True, reason="既有配對"),
        "artifact_targets": ["resume"],
        "company_research_requested": False,
        "quality_review": False,
    })

    result = g.invoke(initial, CONFIG)
    assert "__interrupt__" in result
    assert result["tailored_resume"].summary == "履歷"


def test_route_match_decision():
    # 依 supervisor 決策路由；match 崩潰則強制續做
    assert graph_mod.route_match_decision(
        {"supervisor_decision": SupervisorDecision(next_action="proceed"), "errors": []}
    ) == "company_research"
    assert graph_mod.route_match_decision(
        {"supervisor_decision": SupervisorDecision(next_action="stop"), "errors": []}
    ) == "stop"
    assert graph_mod.route_match_decision(
        {"supervisor_decision": SupervisorDecision(next_action="stop"),
         "errors": [{"node": "match", "message": "boom"}]}
    ) == "company_research"


def test_route_after_generation():
    assert graph_mod.route_after_generation({"quality_review": True}) == "critic"
    assert graph_mod.route_after_generation({"quality_review": False}) == "human_gate"
    assert graph_mod.route_after_generation({}) == "critic"  # 舊 checkpoint 相容
