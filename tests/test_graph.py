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


def _patch_supervisor(monkeypatch):
    # supervisor 用確定性門檻邏輯（不打 LLM），保留原路由語意供其他測試斷言
    monkeypatch.setattr(graph_mod, "supervise_after_match",
                        lambda match, job, profile: SupervisorDecision(
                            next_action="proceed" if (match.recommend_proceed and match.score >= 60)
                            else "stop"))
    monkeypatch.setattr(graph_mod, "supervise_after_critic",
                        lambda critique, rc, mx: SupervisorDecision(
                            next_action="approve" if (critique.overall_pass or rc >= mx) else "revise",
                            docs_to_revise=[d for d in (critique.per_doc or {})]))


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
    _patch_supervisor(monkeypatch)


def _passing_critic(monkeypatch):
    monkeypatch.setattr(graph_mod, "critique_package",
                        lambda job, r, c, k: CritiqueReport(
                            resume_score=90, cover_letter_score=88, interview_score=85,
                            overall_pass=True, feedback=[]))


def _initial(profile):
    return {
        "jd_text": "（任意）", "profile": profile,
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


def test_failing_critic_loops_then_stops_at_max(monkeypatch, demo_profile):
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
    assert calls["critic"] == 3   # MAX_REVISIONS=3：評審 3 次（含 2 次重寫）
    assert calls["resume"] == 3
    assert "__interrupt__" in result


def test_revise_passes_per_doc_feedback_to_generator(monkeypatch, demo_profile):
    _patch_base(monkeypatch, MatchReport(score=82, recommend_proceed=True, reason="吻合"))
    seen = {"feedback": None}

    def resume_capture(job, profile, feedback=None):
        if feedback:
            seen["feedback"] = feedback
        return TailoredResume(summary="x")

    critic_calls = {"n": 0}

    def fail_once(job, r, c, k):
        critic_calls["n"] += 1
        if critic_calls["n"] == 1:
            return CritiqueReport(resume_score=10, cover_letter_score=90, interview_score=90,
                                  overall_pass=False, per_doc={"resume": ["把成果量化"]})
        return CritiqueReport(resume_score=90, cover_letter_score=90, interview_score=90,
                              overall_pass=True)

    monkeypatch.setattr(graph_mod, "tailor_resume", resume_capture)
    monkeypatch.setattr(graph_mod, "critique_package", fail_once)
    g = graph_mod.build_graph()

    g.invoke(_initial(demo_profile), CONFIG)
    assert seen["feedback"] == ["把成果量化"]


def test_targeted_revise_only_reruns_failed_doc(monkeypatch, demo_profile):
    # per_doc 只標 resume → 重寫輪只重跑 resume，cover/interview 不動（省 token）
    _patch_base(monkeypatch, MatchReport(score=82, recommend_proceed=True, reason="吻合"))
    calls = {"resume": 0, "cover": 0, "interview": 0}

    def cnt_resume(job, profile, feedback=None):
        calls["resume"] += 1
        return TailoredResume(summary="r")

    def cnt_cover(job, profile, company, feedback=None):
        calls["cover"] += 1
        return CoverLetter(body="c")

    def cnt_interview(job, profile, company, feedback=None):
        calls["interview"] += 1
        return InterviewKit()

    critic_calls = {"n": 0}

    def fail_resume_once(job, r, c, k):
        critic_calls["n"] += 1
        if critic_calls["n"] == 1:
            return CritiqueReport(resume_score=10, cover_letter_score=90, interview_score=90,
                                  overall_pass=False, per_doc={"resume": ["再加強"]})
        return CritiqueReport(resume_score=90, cover_letter_score=90, interview_score=90,
                              overall_pass=True)

    monkeypatch.setattr(graph_mod, "tailor_resume", cnt_resume)
    monkeypatch.setattr(graph_mod, "write_cover_letter", cnt_cover)
    monkeypatch.setattr(graph_mod, "prepare_interview", cnt_interview)
    monkeypatch.setattr(graph_mod, "critique_package", fail_resume_once)
    g = graph_mod.build_graph()

    g.invoke(_initial(demo_profile), CONFIG)
    assert calls["resume"] == 2      # 首輪 + 重寫
    assert calls["cover"] == 1       # 只跑首輪，未被重跑
    assert calls["interview"] == 1


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


def test_route_critic_decision():
    assert graph_mod.route_critic_decision(
        {"supervisor_decision": SupervisorDecision(next_action="approve")}
    ) == "approve"
    assert graph_mod.route_critic_decision(
        {"supervisor_decision": SupervisorDecision(next_action="revise", docs_to_revise=["resume"])}
    ) == "revise"
