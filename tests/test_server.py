import json

from fastapi.testclient import TestClient

from app.models import (
    ParsedJob, MatchReport, CompanyBrief, TailoredResume, CoverLetter,
    InterviewKit, CritiqueReport,
)
from app import graph as graph_mod
from app import server as server_mod


def _patch_agents(monkeypatch):
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


def _parse_sse(text: str) -> list[dict]:
    events = []
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("data:"):
            events.append(json.loads(line[len("data:"):].strip()))
    return events


def test_sample_endpoint():
    client = TestClient(server_mod.app)
    r = client.get("/api/sample")
    assert r.status_code == 200
    assert "工程師" in r.json()["jd_text"]


def test_run_streams_to_interrupt_then_resume(monkeypatch):
    _patch_agents(monkeypatch)
    client = TestClient(server_mod.app)

    r = client.post("/api/run", json={"jd_text": "一些 JD"})
    assert r.status_code == 200
    events = _parse_sse(r.text)
    types = [e["type"] for e in events]
    assert types[0] == "start"
    assert "node" in types
    assert types[-1] == "interrupt"
    thread_id = events[0]["thread_id"]

    r2 = client.post("/api/resume", json={"thread_id": thread_id, "decision": "y"})
    assert r2.status_code == 200
    ev2 = _parse_sse(r2.text)
    assert ev2[-1]["type"] == "done"
    assert any(e.get("type") == "node" for e in ev2)


def test_run_stop_path_finishes_without_interrupt(monkeypatch):
    _patch_agents(monkeypatch)
    monkeypatch.setattr(graph_mod, "match_profile",
                        lambda job, profile: MatchReport(score=30, recommend_proceed=False, reason="不符"))
    client = TestClient(server_mod.app)
    r = client.post("/api/run", json={"jd_text": "一些 JD"})
    events = _parse_sse(r.text)
    types = [e["type"] for e in events]
    assert "interrupt" not in types
    assert types[-1] == "done"


def test_index_serves_html():
    client = TestClient(server_mod.app)
    r = client.get("/")
    assert r.status_code == 200
    assert "<html" in r.text.lower()
    assert "求職" in r.text  # 確認是我們的頁面而非佔位


def test_resume_evaluate_with_text(monkeypatch):
    from app.models import Profile, ResumeAssessment
    monkeypatch.setattr(server_mod, "structure_profile",
                        lambda text: Profile(name="王小明", summary="後端工程師", raw_text=text))
    monkeypatch.setattr(server_mod, "evaluate_resume",
                        lambda text, profile: ResumeAssessment(
                            overall_score=80, clarity_score=80, impact_score=80,
                            ats_keyword_score=80, localization_score=80,
                            completeness_score=80, summary="不錯"))
    client = TestClient(server_mod.app)
    r = client.post("/api/resume/evaluate", data={"resume_text": "我的履歷 Python"})
    assert r.status_code == 200
    events = _parse_sse(r.text)
    types = [e["type"] for e in events]
    assert types[0] == "start"
    assert "assessment" in types
    assert types[-1] == "done"
    assessment_ev = next(e for e in events if e["type"] == "assessment")
    assert assessment_ev["data"]["overall_score"] == 80


def test_resume_evaluate_empty_returns_error():
    client = TestClient(server_mod.app)
    r = client.post("/api/resume/evaluate", data={"resume_text": "   "})
    events = _parse_sse(r.text)
    assert any(e["type"] == "error" for e in events)


def test_resume_evaluate_handles_agent_error(monkeypatch):
    def boom(text):
        raise RuntimeError("rate limited")
    monkeypatch.setattr(server_mod, "structure_profile", boom)
    client = TestClient(server_mod.app)
    r = client.post("/api/resume/evaluate", data={"resume_text": "履歷文字 Python"})
    assert r.status_code == 200
    events = _parse_sse(r.text)
    types = [e["type"] for e in events]
    assert "error" in types
    assert "assessment" not in types
