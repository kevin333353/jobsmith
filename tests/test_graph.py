from app.models import ParsedJob, MatchReport
from app import graph as graph_mod


def _patch_agents(monkeypatch, report: MatchReport):
    monkeypatch.setattr(
        graph_mod, "parse_job",
        lambda jd_text: ParsedJob(title="AI 工程師", company="未來智能"),
    )
    monkeypatch.setattr(
        graph_mod, "match_profile",
        lambda job, profile: report,
    )


def test_graph_runs_end_to_end(monkeypatch, demo_profile):
    report = MatchReport(score=82, recommend_proceed=True, reason="吻合")
    _patch_agents(monkeypatch, report)

    app_graph = graph_mod.build_graph()
    final = app_graph.invoke({
        "jd_text": "（任意）",
        "profile": demo_profile,
        "parsed_job": None,
        "match_report": None,
    })

    assert final["parsed_job"].company == "未來智能"
    assert final["match_report"].score == 82


def test_route_after_match_proceeds_on_high_score():
    state = {"match_report": MatchReport(score=80, recommend_proceed=True, reason="高")}
    assert graph_mod.route_after_match(state) == "proceed"


def test_route_after_match_stops_when_not_recommended():
    state = {"match_report": MatchReport(score=40, recommend_proceed=False, reason="低")}
    assert graph_mod.route_after_match(state) == "stop"
