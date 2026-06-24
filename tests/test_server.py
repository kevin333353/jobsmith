import json

from fastapi.testclient import TestClient

from app.models import (
    ParsedJob, MatchReport, CompanyBrief, TailoredResume, CoverLetter,
    InterviewKit, CritiqueReport, SupervisorDecision,
)
from app import graph as graph_mod
from app import server as server_mod


def _patch_agents(monkeypatch):
    monkeypatch.setattr(graph_mod, "parse_job",
                        lambda jd_text: ParsedJob(title="AI 工程師", company="未來智能"))
    monkeypatch.setattr(graph_mod, "match_profile",
                        lambda job, profile: MatchReport(score=82, recommend_proceed=True, reason="吻合"))
    monkeypatch.setattr(graph_mod, "supervise_after_match",
                        lambda match, job, profile: SupervisorDecision(
                            next_action="proceed" if (match.recommend_proceed and match.score >= 60)
                            else "stop"))
    monkeypatch.setattr(graph_mod, "supervise_after_critic",
                        lambda critique, rc, mx: SupervisorDecision(
                            next_action="approve" if (critique.overall_pass or rc >= mx) else "revise",
                            docs_to_revise=[d for d in (critique.per_doc or {})]))
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


def test_run_uses_posted_profile_not_demo(monkeypatch):
    # 核心修正：投遞包必須用使用者真實履歷，而非 data/demo_profile.json 的假人
    _patch_agents(monkeypatch)
    seen = {}

    def capture(job, profile, feedback=None):
        seen["name"] = profile.name
        return TailoredResume(summary="履歷")
    monkeypatch.setattr(graph_mod, "tailor_resume", capture)

    client = TestClient(server_mod.app)
    r = client.post("/api/run", json={
        "jd_text": "JD",
        "profile": {"name": "測試真人", "summary": "資深 Agent 工程師", "skills": ["LangGraph"]},
    })
    assert r.status_code == 200
    _parse_sse(r.text)
    assert seen["name"] == "測試真人"      # 用 posted profile
    assert seen["name"] != "陳小安"        # 不是 demo profile


def test_run_falls_back_to_demo_profile_when_absent(monkeypatch):
    _patch_agents(monkeypatch)
    seen = {}

    def capture(job, profile, feedback=None):
        seen["name"] = profile.name
        return TailoredResume(summary="履歷")
    monkeypatch.setattr(graph_mod, "tailor_resume", capture)

    client = TestClient(server_mod.app)
    r = client.post("/api/run", json={"jd_text": "JD"})  # 不帶 profile
    _parse_sse(r.text)
    assert seen["name"] == "陳小安"        # 後備 demo profile


def test_run_degrades_gracefully_on_agent_failure(monkeypatch):
    # 單一 agent 例外不應炸掉整條 SSE：仍走到人工關卡，並發 node_error 提示
    _patch_agents(monkeypatch)

    def boom(job, profile, feedback=None):
        raise RuntimeError("LLM 暫時爆了")
    monkeypatch.setattr(graph_mod, "tailor_resume", boom)

    client = TestClient(server_mod.app)
    r = client.post("/api/run", json={"jd_text": "JD"})
    events = _parse_sse(r.text)
    types = [e["type"] for e in events]
    assert "node_error" in types
    assert types[-1] == "interrupt"        # 流程沒被中斷
    err = next(e for e in events if e["type"] == "node_error")
    assert err["node"] == "resume_tailor"


def test_run_continues_when_match_agent_crashes(monkeypatch):
    # match agent 崩潰不可被誤判為「低適配 → 停止」：仍要產出降級投遞包並走到人工關卡
    _patch_agents(monkeypatch)

    def boom(job, profile):
        raise RuntimeError("match LLM 429")
    monkeypatch.setattr(graph_mod, "match_profile", boom)

    client = TestClient(server_mod.app)
    r = client.post("/api/run", json={"jd_text": "JD"})
    events = _parse_sse(r.text)
    types = [e["type"] for e in events]
    assert types[-1] == "interrupt"        # 沒有在 match 後就 stop
    assert any(e.get("type") == "node_error" and e.get("node") == "match" for e in events)
    nodes = [e.get("node") for e in events if e.get("type") == "node"]
    assert "resume_tailor" in nodes        # 下游降級投遞包仍有產出


def test_run_partial_profile_returns_sse_error_not_500(monkeypatch):
    # 缺必填欄位的 profile 應回友善 SSE error（在 generator 內），而非 500
    _patch_agents(monkeypatch)
    client = TestClient(server_mod.app)
    r = client.post("/api/run", json={"jd_text": "JD", "profile": {"skills": ["x"]}})
    assert r.status_code == 200            # 串流本身成功
    events = _parse_sse(r.text)
    assert events[0]["type"] == "start"
    assert any(e["type"] == "error" for e in events)
    assert not any(e["type"] == "node" for e in events)


def test_run_warns_when_using_demo_profile(monkeypatch):
    # 未帶真實履歷 → 用 demo，但要明確發 profile_warning 提醒
    _patch_agents(monkeypatch)
    client = TestClient(server_mod.app)
    r = client.post("/api/run", json={"jd_text": "JD"})
    events = _parse_sse(r.text)
    assert any(e["type"] == "profile_warning" for e in events)


def test_run_no_warning_when_real_profile(monkeypatch):
    _patch_agents(monkeypatch)
    client = TestClient(server_mod.app)
    r = client.post("/api/run", json={
        "jd_text": "JD", "profile": {"name": "真人", "summary": "工程師"}})
    events = _parse_sse(r.text)
    assert not any(e["type"] == "profile_warning" for e in events)


def test_run_emits_per_node_telemetry(monkeypatch):
    # 每個經 _safe 的節點都應發 telemetry 事件（含延遲；mock 下 token=0）
    _patch_agents(monkeypatch)
    client = TestClient(server_mod.app)
    r = client.post("/api/run", json={
        "jd_text": "JD", "profile": {"name": "真人", "summary": "工程師"}})
    events = _parse_sse(r.text)
    tel = [e for e in events if e["type"] == "telemetry"]
    assert tel, "應發出逐節點 telemetry"
    assert all("node" in t and "latency_ms" in t for t in tel)
    nodes = {t["node"] for t in tel}
    assert "parse" in nodes and "match" in nodes


def test_run_telemetry_attributes_tokens_to_correct_node(monkeypatch):
    # 回歸：非首節點的 token 也要記到（修 contextvar 跨 SSE threadpool yield 遺失的 bug）
    from app import telemetry as tele
    _patch_agents(monkeypatch)

    def match_with_usage(job, profile):
        tele.record_llm(input_tokens=100, output_tokens=50, cost_usd=0.01)
        return MatchReport(score=82, recommend_proceed=True, reason="吻合")
    monkeypatch.setattr(graph_mod, "match_profile", match_with_usage)

    client = TestClient(server_mod.app)
    r = client.post("/api/run", json={"jd_text": "JD", "profile": {"name": "x", "summary": "y"}})
    tel = {e["node"]: e for e in _parse_sse(r.text) if e["type"] == "telemetry"}
    assert tel["match"]["input_tokens"] == 100   # match 是非首節點，仍正確歸帳
    assert tel["match"]["output_tokens"] == 50
    assert tel["match"]["calls"] == 1
    assert tel["parse"]["input_tokens"] == 0     # 未呼叫 record 的節點為 0，無交叉計數


def test_jobs_auto_falls_back_when_all_blocked(monkeypatch):
    from app.models import Profile, JobMatch, SearchResult
    monkeypatch.setattr(server_mod, "structure_profile",
                        lambda text: Profile(name="王", summary="後端", raw_text=text))
    monkeypatch.setattr(server_mod, "derive_queries", lambda profile: ["AI 工程師"])
    # 所有來源都被擋 → 無 job
    monkeypatch.setattr(server_mod, "search_all",
                        lambda q, limit=10: [SearchResult(source="104", blocked=True)])
    captured = {}

    def fake_rank(profile, jobs, top_k=12):
        captured["n"] = len(jobs)
        return [JobMatch(job=jobs[0], fit_score=50, reason="範例")] if jobs else []
    monkeypatch.setattr(server_mod, "rank_jobs", fake_rank)

    client = TestClient(server_mod.app)
    r = client.post("/api/jobs/auto", data={"resume_text": "我的履歷"})
    events = _parse_sse(r.text)
    types = [e["type"] for e in events]
    assert "all_blocked" in types          # 誠實告知來源失敗
    assert captured["n"] > 0               # 改用後備樣本職缺
    rs = next(e for e in events if e["type"] == "rank_start")
    assert rs["fallback"] is True          # fallback 旗標改放 rank_start


def test_jobs_auto_emits_profile_event(monkeypatch):
    from app.models import Profile, JobPosting, JobMatch, SearchResult
    monkeypatch.setattr(server_mod, "structure_profile",
                        lambda text: Profile(name="王小明", summary="後端", raw_text=text,
                                             skills=["Python"]))
    monkeypatch.setattr(server_mod, "derive_queries", lambda profile: ["AI 工程師"])
    monkeypatch.setattr(server_mod, "search_all",
                        lambda q, limit=10: [SearchResult(source="104", jobs=[
                            JobPosting(source="104", title="AI", company="C", url="u1")])])
    monkeypatch.setattr(server_mod, "rank_jobs",
                        lambda profile, jobs, top_k=12: [JobMatch(job=jobs[0], fit_score=80)])
    client = TestClient(server_mod.app)
    r = client.post("/api/jobs/auto", data={"resume_text": "我的履歷原文 Python"})
    events = _parse_sse(r.text)
    prof = next(e for e in events if e["type"] == "profile")
    assert prof["data"]["name"] == "王小明"
    assert prof["data"]["raw_text"] == "我的履歷原文 Python"  # 含原文供 pipeline 帶入


def test_get_backend_lists_cli_options():
    client = TestClient(server_mod.app)
    r = client.get("/api/backend")
    assert r.status_code == 200
    data = r.json()
    ids = [o["id"] for o in data["options"]]
    assert "claude_cli" in ids and "codex_cli" in ids
    assert "current" in data
    assert all("available" in o and "label" in o for o in data["options"])


def test_post_backend_switches_and_rejects_unsupported():
    client = TestClient(server_mod.app)
    try:
        ok = client.post("/api/backend", json={"backend": "codex_cli"})
        assert ok.status_code == 200 and ok.json()["current"] == "codex_cli"
        bad = client.post("/api/backend", json={"backend": "qianfan"})
        assert bad.status_code == 400
    finally:
        client.post("/api/backend", json={"backend": "claude_cli"})  # 還原


def test_backend_test_reports_success(monkeypatch):
    monkeypatch.setattr(server_mod, "_backend_available", lambda name: True)
    monkeypatch.setattr(server_mod, "_probe_claude", lambda: "你好")
    client = TestClient(server_mod.app)
    r = client.post("/api/backend/test", json={"backend": "claude_cli"})
    assert r.status_code == 200 and r.json()["ok"] is True


def test_backend_test_unavailable_skips_probe(monkeypatch):
    monkeypatch.setattr(server_mod, "_backend_available", lambda name: False)
    called = {"n": 0}
    monkeypatch.setattr(server_mod, "_probe_claude", lambda: called.__setitem__("n", 1) or "你好")
    client = TestClient(server_mod.app)
    r = client.post("/api/backend/test", json={"backend": "claude_cli"})
    assert r.status_code == 200 and r.json()["ok"] is False
    assert called["n"] == 0  # 不可用就不該真的去打 CLI


def test_backend_test_rejects_unsupported():
    client = TestClient(server_mod.app)
    r = client.post("/api/backend/test", json={"backend": "qianfan"})
    assert r.status_code == 400


def test_backend_test_reports_failure_on_probe_error(monkeypatch):
    monkeypatch.setattr(server_mod, "_backend_available", lambda name: True)
    def boom():
        raise RuntimeError("not logged in")
    monkeypatch.setattr(server_mod, "_probe_claude", boom)
    client = TestClient(server_mod.app)
    r = client.post("/api/backend/test", json={"backend": "claude_cli"})
    assert r.status_code == 200 and r.json()["ok"] is False


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


def test_jobs_auto_streams_ranked_jobs(monkeypatch):
    from app.models import Profile, JobPosting, JobMatch, SearchResult
    monkeypatch.setattr(server_mod, "structure_profile",
                        lambda text: Profile(name="王", summary="後端", raw_text=text))
    monkeypatch.setattr(server_mod, "derive_queries", lambda profile: ["AI 工程師"])
    monkeypatch.setattr(server_mod, "search_all",
                        lambda q, limit=10: [SearchResult(source="104", jobs=[
                            JobPosting(source="104", title="AI 工程師", company="某公司", url="u1")])])
    monkeypatch.setattr(server_mod, "rank_jobs",
                        lambda profile, jobs, top_k=12: [JobMatch(job=jobs[0], fit_score=88, reason="合適")])
    client = TestClient(server_mod.app)
    r = client.post("/api/jobs/auto", data={"resume_text": "我的履歷 Python"})
    assert r.status_code == 200
    events = _parse_sse(r.text)
    types = [e["type"] for e in events]
    assert types[0] == "start"
    assert "queries" in types and "ranked_batch" in types  # 改為分批串流
    assert types[-1] == "done"
    ranked = [m for e in events if e["type"] == "ranked_batch" for m in e["data"]]
    assert ranked[0]["fit_score"] == 88
    assert ranked[0]["job"]["title"] == "AI 工程師"


def test_jobs_auto_empty_returns_error():
    client = TestClient(server_mod.app)
    r = client.post("/api/jobs/auto", data={"resume_text": "  "})
    events = _parse_sse(r.text)
    assert any(e["type"] == "error" for e in events)


def test_jobs_auto_lists_company_jobs_in_separate_event(monkeypatch):
    """指定公司名單時，公司開缺走獨立的 company_jobs 事件、與 AI 推薦分開排序。"""
    from app.models import Profile, JobPosting, JobMatch, SearchResult
    monkeypatch.setattr(server_mod, "structure_profile",
                        lambda text: Profile(name="王", summary="後端", raw_text=text))
    monkeypatch.setattr(server_mod, "derive_queries", lambda profile: ["AI 工程師"])
    monkeypatch.setattr(server_mod, "search_all",
                        lambda q, limit=15: [SearchResult(source="104", jobs=[
                            JobPosting(source="104", title="AI 工程師", company="某公司", url="u1")])])
    captured = {}

    def fake_find(company, profile=None):
        captured.setdefault("companies", []).append(company)
        return [JobPosting(source="careers", title="ML Engineer", company=company,
                           url=f"https://{company}.com/jobs/ml")]
    monkeypatch.setattr(server_mod, "find_company_jobs", fake_find)
    monkeypatch.setattr(server_mod, "rank_jobs",
                        lambda profile, jobs, top_k=None: [JobMatch(job=j, fit_score=70) for j in jobs])

    client = TestClient(server_mod.app)
    r = client.post("/api/jobs/auto",
                    data={"resume_text": "我的履歷 Python", "companies": "Google、華碩"})
    events = _parse_sse(r.text)
    assert captured["companies"] == ["Google", "華碩"]
    ai_titles = {m["job"]["title"] for e in events if e["type"] == "ranked_batch" for m in e["data"]}
    assert ai_titles == {"AI 工程師"}                 # AI 推薦只含履歷搜尋結果
    comp_ev = next(e for e in events if e["type"] == "company_jobs")
    comp_titles = {m["job"]["title"] for m in comp_ev["data"]}
    assert comp_titles == {"ML Engineer"}            # 公司開缺在獨立區塊


def test_jobs_auto_without_companies_skips_company_lookup(monkeypatch):
    from app.models import Profile, JobPosting, JobMatch, SearchResult
    monkeypatch.setattr(server_mod, "structure_profile",
                        lambda text: Profile(name="王", summary="後端", raw_text=text))
    monkeypatch.setattr(server_mod, "derive_queries", lambda profile: ["AI 工程師"])
    monkeypatch.setattr(server_mod, "search_all",
                        lambda q, limit=15: [SearchResult(source="104", jobs=[
                            JobPosting(source="104", title="AI 工程師", company="某公司", url="u1")])])
    called = {"n": 0}

    def fake_find(company, profile=None):
        called["n"] += 1
        return []
    monkeypatch.setattr(server_mod, "find_company_jobs", fake_find)
    monkeypatch.setattr(server_mod, "rank_jobs",
                        lambda profile, jobs, top_k=None: [JobMatch(job=j, fit_score=70) for j in jobs])

    client = TestClient(server_mod.app)
    r = client.post("/api/jobs/auto", data={"resume_text": "我的履歷 Python"})
    assert r.status_code == 200
    assert called["n"] == 0  # 沒填公司名單就不查公司
