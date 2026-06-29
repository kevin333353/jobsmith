import json

from fastapi.testclient import TestClient

from app import graph as graph_mod
from app import server as server_mod
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
from tests.conftest import FakeLLM


def test_err_detail_surfaces_real_reason(monkeypatch):
    # 視窗版 exe 沒 console：只印類別名稱（RuntimeError）無從診斷，必須帶出真正訊息。
    # 日誌寫檔是 best-effort（自帶 try/except），故導向不可寫路徑也不能讓回傳壞掉。
    monkeypatch.setattr(server_mod, "_ERROR_LOG", server_mod.Path("?:/nope/error.log"))
    detail = server_mod._err_detail(RuntimeError("claude CLI 失敗（rc=1）：model not available"))
    assert detail.startswith("RuntimeError: ")
    assert "claude CLI 失敗" in detail
    assert "model not available" in detail


def test_ensure_backend_live_blocks_when_probe_fails(monkeypatch):
    # AI 接不通（沒登入）→ 把關回 (False, 引導訊息)，上層據此中止搜尋、不靜默降級。
    server_mod.mark_backend_unverified()
    monkeypatch.setattr(server_mod, "_backend_available", lambda name: True)
    monkeypatch.setattr(server_mod, "_probe_backend",
                        lambda name: (_ for _ in ()).throw(RuntimeError("not logged in")))
    ok, msg = server_mod.ensure_backend_live("claude_cli")
    assert ok is False and "登入" in msg


def test_ensure_backend_live_blocks_when_unavailable(monkeypatch):
    server_mod.mark_backend_unverified()
    monkeypatch.setattr(server_mod, "_backend_available", lambda name: False)
    ok, msg = server_mod.ensure_backend_live("claude_cli")
    assert ok is False and "找不到" in msg


def test_ensure_backend_live_blocks_on_empty_reply(monkeypatch):
    server_mod.mark_backend_unverified()
    monkeypatch.setattr(server_mod, "_backend_available", lambda name: True)
    monkeypatch.setattr(server_mod, "_probe_backend", lambda name: "   ")
    ok, _ = server_mod.ensure_backend_live("claude_cli")
    assert ok is False


def test_ensure_backend_live_passes_and_caches(monkeypatch):
    # 探測通過後快取：同一後端/模型的後續搜尋不再重複探測（省 ~2 秒/次）。
    server_mod.mark_backend_unverified()
    monkeypatch.setattr(server_mod, "_backend_available", lambda name: True)
    calls = {"n": 0}

    def probe(name):
        calls["n"] += 1
        return "1"

    monkeypatch.setattr(server_mod, "_probe_backend", probe)
    assert server_mod.ensure_backend_live("claude_cli")[0] is True
    assert server_mod.ensure_backend_live("claude_cli")[0] is True
    assert calls["n"] == 1


def test_switch_model_invalidates_probe_cache(monkeypatch):
    # 換模型 → 快取失效，下次搜尋重新探測（不拿舊模型的「接得通」當新模型保證）。
    server_mod.mark_backend_verified("claude_cli")
    sig = server_mod._backend_signature("claude_cli")
    assert sig in server_mod._backend_live_at
    server_mod.mark_backend_unverified("claude_cli")
    assert sig not in server_mod._backend_live_at


class _FakeResp:
    def __init__(self, ok, data):
        self.ok = ok
        self._data = data

    def json(self):
        return self._data


def test_parse_version_handles_prefixes_and_partials():
    assert server_mod._parse_version("v0.2.0") == (0, 2, 0)
    assert server_mod._parse_version("0.1") == (0, 1, 0)
    assert server_mod._parse_version("1.2.3-beta.1") == (1, 2, 3)
    assert server_mod._parse_version("nonsense") == ()
    assert server_mod._parse_version("v1.0.0") > server_mod._parse_version("0.9.9")


def test_check_for_update_flags_newer_release(monkeypatch):
    monkeypatch.setattr(server_mod, "__version__", "0.1.0")
    monkeypatch.setattr(server_mod.requests, "get",
                        lambda *a, **k: _FakeResp(True, {"tag_name": "v0.2.0", "html_url": "u"}))
    out = server_mod.check_for_update()
    assert out["update_available"] is True
    assert out["latest"] == "v0.2.0" and out["url"] == "u"


def test_check_for_update_no_update_when_not_newer(monkeypatch):
    monkeypatch.setattr(server_mod, "__version__", "0.2.0")
    monkeypatch.setattr(server_mod.requests, "get",
                        lambda *a, **k: _FakeResp(True, {"tag_name": "v0.2.0"}))
    assert server_mod.check_for_update()["update_available"] is False


def test_check_for_update_silent_on_error(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("offline")

    monkeypatch.setattr(server_mod.requests, "get", boom)
    out = server_mod.check_for_update()
    assert out["update_available"] is False and out["latest"] is None


def test_update_check_endpoint(monkeypatch):
    monkeypatch.setattr(server_mod, "check_for_update",
                        lambda: {"current": "0.1.0", "latest": "v0.2.0",
                                 "update_available": True, "url": "u"})
    client = TestClient(server_mod.app)
    r = client.get("/api/update-check")
    assert r.status_code == 200 and r.json()["update_available"] is True


def test_app_version_matches_pyproject():
    # 防版本漂移：app.__version__（執行期/exe 用）必須與 pyproject.toml 一致。
    import pathlib
    import re as _re
    txt = pathlib.Path("pyproject.toml").read_text(encoding="utf-8")
    m = _re.search(r'^version\s*=\s*"([^"]+)"', txt, _re.M)
    assert m and m.group(1) == server_mod.__version__


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


def _run_bg(client, payload):
    """背景產生：POST /api/run 後等該 run 的 future 完成（確定性），回 (resp_json, events)。"""
    r = client.post("/api/run", json=payload)
    assert r.status_code == 200, r.text
    d = r.json()
    server_mod._RUNS[d["thread_id"]].future.result(timeout=15)  # 等背景跑完
    events = client.get(f"/api/run/events/{d['thread_id']}").json()["events"]
    return d, events


def test_run_creates_record_immediately_and_returns_ids(monkeypatch):
    # 一按產生投遞包就回 thread_id/package_id，且「我的投遞包」立刻有一筆紀錄。
    _patch_agents(monkeypatch)
    client = TestClient(server_mod.app)
    r = client.post("/api/run", json={"jd_text": "JD"})
    assert r.status_code == 200
    d = r.json()
    assert isinstance(d["thread_id"], str) and isinstance(d["package_id"], int)
    assert server_mod._history.get_package(d["package_id"]) is not None
    server_mod._RUNS[d["thread_id"]].future.result(timeout=15)  # 等背景跑完，避免 unpatch 後跑到真 agent


def test_run_completes_in_background_and_saves_pending(monkeypatch):
    # 背景跑到底、不停核可關卡；done 帶 package_id；該筆存成 done 且待審(approved=0)。
    _patch_agents(monkeypatch)
    client = TestClient(server_mod.app)
    d, events = _run_bg(client, {"jd_text": "一些 JD"})
    types = [e["type"] for e in events]
    assert "interrupt" not in types and "node" in types and types[-1] == "done"
    assert events[-1]["package_id"] == d["package_id"]
    full = server_mod._history.get_package(d["package_id"])
    assert full["status"] == "done" and full["approved"] == 0


def test_two_runs_complete_independently(monkeypatch):
    # 平行：兩個產生各用獨立 graph/checkpointer，都能完成（不互卡、不共用狀態）。
    _patch_agents(monkeypatch)
    client = TestClient(server_mod.app)
    a = client.post("/api/run", json={"jd_text": "JD A"}).json()
    b = client.post("/api/run", json={"jd_text": "JD B"}).json()
    server_mod._RUNS[a["thread_id"]].future.result(timeout=20)
    server_mod._RUNS[b["thread_id"]].future.result(timeout=20)
    assert server_mod._history.get_package(a["package_id"])["status"] == "done"
    assert server_mod._history.get_package(b["package_id"])["status"] == "done"


def test_run_events_unknown_thread_returns_not_found():
    # 不在記憶體的 thread（已清理/伺服器重啟）→ found=False，前端改從歷史載入。
    client = TestClient(server_mod.app)
    d = client.get("/api/run/events/does-not-exist").json()
    assert d["found"] is False and d["done"] is True


def test_run_stop_endpoint_marks_backend_state_stopped():
    client = TestClient(server_mod.app)
    thread_id = "thread-stop-test"
    pid = server_mod._history.create_running_package(thread_id, "JD", "T", None)
    run = server_mod._Run(thread_id, pid)

    class FakeFuture:
        def __init__(self):
            self.cancelled = False

        def cancel(self):
            self.cancelled = True
            return True

    future = FakeFuture()
    run.future = future
    with server_mod._RUNS_LOCK:
        server_mod._RUNS[thread_id] = run
    try:
        r = client.post(f"/api/run/{thread_id}/stop")
        assert r.status_code == 200
        assert r.json()["status"] == "stopped"
        assert future.cancelled is True
        assert server_mod._history.get_package(pid)["status"] == "stopped"
        events = client.get(f"/api/run/events/{thread_id}").json()
        assert events["done"] is True
        assert any(e["type"] == "stopped" for e in events["events"])
    finally:
        with server_mod._RUNS_LOCK:
            server_mod._RUNS.pop(thread_id, None)
        server_mod._history.delete_package(pid)


def test_run_stop_path_finalizes_record(monkeypatch):
    # 低適配 → supervisor 停做：仍要收尾成 stopped（不卡「進行中」，也不冒充待審成品）。
    _patch_agents(monkeypatch)
    monkeypatch.setattr(graph_mod, "match_profile",
                        lambda job, profile: MatchReport(score=30, recommend_proceed=False, reason="不符"))
    client = TestClient(server_mod.app)
    d, events = _run_bg(client, {"jd_text": "一些 JD"})
    types = [e["type"] for e in events]
    assert "interrupt" not in types and types[-1] == "done"
    full = server_mod._history.get_package(d["package_id"])
    assert full["status"] == "stopped" and full["has_artifacts"] == 0


def test_run_uses_posted_profile_not_demo(monkeypatch):
    # 核心修正：投遞包必須用使用者真實履歷，而非 data/demo_profile.json 的假人
    _patch_agents(monkeypatch)
    seen = {}

    def capture(job, profile, feedback=None):
        seen["name"] = profile.name
        return TailoredResume(summary="履歷")
    monkeypatch.setattr(graph_mod, "tailor_resume", capture)

    client = TestClient(server_mod.app)
    _run_bg(client, {
        "jd_text": "JD",
        "profile": {"name": "測試真人", "summary": "資深 Agent 工程師", "skills": ["LangGraph"]},
    })
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
    _run_bg(client, {"jd_text": "JD"})  # 不帶 profile
    assert seen["name"] == "陳小安"        # 後備 demo profile


def test_run_degrades_gracefully_on_agent_failure(monkeypatch):
    # 單一 agent 例外不應炸掉整條流程：仍跑到底，並發 node_error 提示
    _patch_agents(monkeypatch)

    def boom(job, profile, feedback=None):
        raise RuntimeError("LLM 暫時爆了")
    monkeypatch.setattr(graph_mod, "tailor_resume", boom)

    client = TestClient(server_mod.app)
    d, events = _run_bg(client, {"jd_text": "JD"})
    types = [e["type"] for e in events]
    assert "node_error" in types
    assert types[-1] == "done"             # 流程沒被中斷
    err = next(e for e in events if e["type"] == "node_error")
    assert err["node"] == "resume_tailor"


def test_run_continues_when_match_agent_crashes(monkeypatch):
    # match agent 崩潰不可被誤判為「低適配 → 停止」：仍要產出降級投遞包並跑到底
    _patch_agents(monkeypatch)

    def boom(job, profile):
        raise RuntimeError("match LLM 429")
    monkeypatch.setattr(graph_mod, "match_profile", boom)

    client = TestClient(server_mod.app)
    d, events = _run_bg(client, {"jd_text": "JD"})
    types = [e["type"] for e in events]
    assert types[-1] == "done"             # 沒有在 match 後就 stop
    assert any(e.get("type") == "node_error" and e.get("node") == "match" for e in events)
    nodes = [e.get("node") for e in events if e.get("type") == "node"]
    assert "resume_tailor" in nodes        # 下游降級投遞包仍有產出


def test_run_partial_profile_returns_400_not_500(monkeypatch):
    # 缺必填欄位的 profile 應回 400 友善訊息，而非 500（且不建立進行中紀錄）
    _patch_agents(monkeypatch)
    client = TestClient(server_mod.app)
    r = client.post("/api/run", json={"jd_text": "JD", "profile": {"skills": ["x"]}})
    assert r.status_code == 400
    assert "error" in r.json()


def test_run_warns_when_using_demo_profile(monkeypatch):
    # 未帶真實履歷 → 用 demo，但要明確發 profile_warning 提醒
    _patch_agents(monkeypatch)
    client = TestClient(server_mod.app)
    _, events = _run_bg(client, {"jd_text": "JD"})
    assert any(e["type"] == "profile_warning" for e in events)


def test_run_no_warning_when_real_profile(monkeypatch):
    _patch_agents(monkeypatch)
    client = TestClient(server_mod.app)
    _, events = _run_bg(client, {"jd_text": "JD", "profile": {"name": "真人", "summary": "工程師"}})
    assert not any(e["type"] == "profile_warning" for e in events)


def test_run_emits_per_node_telemetry(monkeypatch):
    # 每個經 _safe 的節點都應發 telemetry 事件（含延遲；mock 下 token=0）
    _patch_agents(monkeypatch)
    client = TestClient(server_mod.app)
    _, events = _run_bg(client, {"jd_text": "JD", "profile": {"name": "真人", "summary": "工程師"}})
    tel = [e for e in events if e["type"] == "telemetry"]
    assert tel, "應發出逐節點 telemetry"
    assert all("node" in t and "latency_ms" in t for t in tel)
    nodes = {t["node"] for t in tel}
    assert "parse" in nodes and "match" in nodes


def test_run_telemetry_attributes_tokens_to_correct_node(monkeypatch):
    # 回歸：非首節點的 token 也要正確歸帳到該節點。
    from app import telemetry as tele
    _patch_agents(monkeypatch)

    def match_with_usage(job, profile):
        tele.record_llm(input_tokens=100, output_tokens=50, cost_usd=0.01)
        return MatchReport(score=82, recommend_proceed=True, reason="吻合")
    monkeypatch.setattr(graph_mod, "match_profile", match_with_usage)

    client = TestClient(server_mod.app)
    _, events = _run_bg(client, {"jd_text": "JD", "profile": {"name": "x", "summary": "y"}})
    tel = {e["node"]: e for e in events if e["type"] == "telemetry"}
    assert tel["match"]["input_tokens"] == 100   # match 是非首節點，仍正確歸帳
    assert tel["match"]["output_tokens"] == 50
    assert tel["match"]["calls"] == 1
    assert tel["parse"]["input_tokens"] == 0     # 未呼叫 record 的節點為 0，無交叉計數


def test_jobs_auto_falls_back_when_all_blocked(monkeypatch):
    from app.models import JobMatch, Profile, SearchResult
    monkeypatch.setattr(server_mod, "structure_profile",
                        lambda text: Profile(name="王", summary="後端", raw_text=text))
    monkeypatch.setattr(server_mod, "derive_queries", lambda profile: ["AI 工程師"])
    # 所有來源都被擋 → 無 job
    monkeypatch.setattr(server_mod, "search_all",
                        lambda q, limit=10, pages=1, area=None: [SearchResult(source="104", blocked=True)])
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
    from app.models import JobMatch, JobPosting, Profile, SearchResult
    monkeypatch.setattr(server_mod, "structure_profile",
                        lambda text: Profile(name="王小明", summary="後端", raw_text=text,
                                             skills=["Python"]))
    monkeypatch.setattr(server_mod, "derive_queries", lambda profile: ["AI 工程師"])
    monkeypatch.setattr(server_mod, "search_all",
                        lambda q, limit=10, pages=1, area=None: [SearchResult(source="104", jobs=[
                            JobPosting(source="104", title="AI", company="C", url="u1")])])
    monkeypatch.setattr(server_mod, "rank_jobs",
                        lambda profile, jobs, top_k=12: [JobMatch(job=jobs[0], fit_score=80)])
    client = TestClient(server_mod.app)
    r = client.post("/api/jobs/auto", data={"resume_text": "我的履歷原文 Python"})
    events = _parse_sse(r.text)
    prof = next(e for e in events if e["type"] == "profile")
    assert prof["data"]["name"] == "王小明"
    assert prof["data"]["raw_text"] == "我的履歷原文 Python"  # 含原文供 pipeline 帶入


def test_jobs_auto_reuses_posted_profile_json_without_reparsing(monkeypatch):
    from app.models import JobMatch, JobPosting, SearchResult

    def fail_structure_profile(text):
        raise AssertionError("structure_profile should not run when profile_json is provided")

    captured = {}
    monkeypatch.setattr(server_mod, "structure_profile", fail_structure_profile)
    monkeypatch.setattr(server_mod, "derive_queries", lambda profile: ["Python 後端"])

    def fake_search(q, limit=10, pages=1, area=None):
        captured["query"] = q
        captured["area"] = area
        return [SearchResult(source="104", jobs=[
            JobPosting(source="104", title="後端工程師", company="C", url="u1",
                       location="台北市信義區"),
        ])]

    def fake_rank(profile, jobs, top_k=None):
        captured["profile_name"] = profile.name
        return [JobMatch(job=jobs[0], fit_score=88)]

    monkeypatch.setattr(server_mod, "search_all", fake_search)
    monkeypatch.setattr(server_mod, "rank_jobs", fake_rank)

    client = TestClient(server_mod.app)
    r = client.post("/api/jobs/auto", data={
        "profile_json": json.dumps({
            "name": "王小明",
            "summary": "Python 後端工程師",
            "skills": ["Python", "FastAPI"],
            "raw_text": "已解析過的履歷",
        }),
        "region": "台北市",
    })

    events = _parse_sse(r.text)
    assert r.status_code == 200
    assert not any(e["type"] == "error" for e in events)
    assert next(e for e in events if e["type"] == "profile")["data"]["name"] == "王小明"
    assert captured["profile_name"] == "王小明"
    assert captured["query"] == "Python 後端"
    assert captured["area"] == ["6001001000"]


def test_jobs_auto_repairs_empty_profile_from_parser(monkeypatch):
    from app.models import Profile, SearchResult

    monkeypatch.setattr(server_mod, "structure_profile", server_mod.structure_profile)
    monkeypatch.setattr(server_mod, "derive_queries", lambda profile: ["工程師"])
    monkeypatch.setattr(server_mod, "search_all",
                        lambda q, limit=15, pages=1, area=None: [SearchResult(source="104")])
    monkeypatch.setattr(server_mod, "_load_fallback_jobs", lambda: [])

    from app.agents import resume_eval as resume_eval_mod
    monkeypatch.setattr(resume_eval_mod, "get_llm",
                        lambda tier: FakeLLM(Profile(name="", summary="", raw_text="")))

    client = TestClient(server_mod.app)
    r = client.post("/api/jobs/auto", data={
        "resume_text": "Alex Chen\nFull Stack Engineer\nPython FastAPI React PostgreSQL"
    })
    events = _parse_sse(r.text)
    profile = next(e["data"] for e in events if e["type"] == "profile")

    assert profile["name"]
    assert profile["summary"]
    assert profile["skills"]


def test_rank_in_batches_falls_back_when_ranker_raises(monkeypatch):
    from app.models import JobPosting, Profile

    def fail_rank(profile, jobs, top_k=None):
        raise RuntimeError("empty rankings from backend")

    monkeypatch.setattr(server_mod, "rank_jobs", fail_rank)
    profile = Profile(name="王", summary="後端", skills=["Python"], raw_text="r")
    jobs = [
        JobPosting(source="104", title="Python 後端工程師", company="C", url="u1",
                   snippet="FastAPI Python"),
        JobPosting(source="104", title="行銷企劃", company="C", url="u2",
                   snippet="社群內容"),
    ]

    batches = list(server_mod._rank_in_batches(profile, jobs, batch=2, workers=1))
    ranked = [m for batch in batches for m in batch]

    assert ranked[0].job.title == "Python 後端工程師"
    assert ranked[0].fit_score > ranked[1].fit_score
    assert ranked[0].reason != "未評分"


def test_get_backend_lists_cli_options():
    client = TestClient(server_mod.app)
    r = client.get("/api/backend")
    assert r.status_code == 200
    data = r.json()
    ids = [o["id"] for o in data["options"]]
    assert "claude_cli" in ids and "codex_cli" in ids
    assert "current" in data
    assert all("available" in o and "label" in o for o in data["options"])


def test_post_backend_switches_and_rejects_unsupported(monkeypatch):
    from pathlib import Path
    env = Path("_backend_switch_test.env")
    env.unlink(missing_ok=True)
    monkeypatch.setenv("COPILOT_ENV_FILE", str(env))
    client = TestClient(server_mod.app)
    try:
        ok = client.post("/api/backend", json={"backend": "codex_cli"})
        assert ok.status_code == 200 and ok.json()["current"] == "codex_cli"
        bad = client.post("/api/backend", json={"backend": "qianfan"})
        assert bad.status_code == 400
    finally:
        client.post("/api/backend", json={"backend": "claude_cli"})  # 還原
        env.unlink(missing_ok=True)


def test_post_backend_persists_selection_for_restart(monkeypatch):
    from pathlib import Path
    env = Path("_backend_server_test.env")
    env.unlink(missing_ok=True)
    monkeypatch.setenv("COPILOT_ENV_FILE", str(env))
    client = TestClient(server_mod.app)
    try:
        r = client.post("/api/backend", json={"backend": "codex_cli"})

        assert r.status_code == 200
        assert "LLM_BACKEND=codex_cli" in env.read_text(encoding="utf-8")
    finally:
        client.post("/api/backend", json={"backend": "claude_cli"})
        env.unlink(missing_ok=True)


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


def test_get_backend_includes_byok_and_cli_models():
    client = TestClient(server_mod.app)
    d = client.get("/api/backend").json()
    ids = [o["id"] for o in d["options"]]
    assert "openai" in ids                                 # BYOK 後端也列出
    assert all("kind" in o for o in d["options"])          # 帶後端類型
    assert d["cli_models"]["claude_cli"]["current"] == "auto"
    assert d["cli_models"]["claude_cli"]["choices"] == ["auto"]
    assert d["cli_models"]["codex_cli"]["choices"] == ["auto"]
    assert "has_key" in d["byok"]                          # 不外洩金鑰本身


def test_post_backend_model_sets_and_rejects():
    client = TestClient(server_mod.app)
    try:
        ok = client.post("/api/backend/model", json={"backend": "claude_cli", "model": "auto"})
        assert ok.status_code == 200 and ok.json()["model"] == "auto"
        invalid_model = client.post("/api/backend/model", json={"backend": "claude_cli", "model": "sonnet"})
        assert invalid_model.status_code == 400             # 不硬編碼列出未偵測模型
        bad = client.post("/api/backend/model", json={"backend": "anthropic", "model": "x"})
        assert bad.status_code == 400                      # 非 CLI 後端不可選模型
    finally:
        client.post("/api/backend/model", json={"backend": "claude_cli", "model": "auto"})


def test_post_backend_byok_saves(monkeypatch):
    from pathlib import Path
    env = Path("_byok_server_test.env")
    env.unlink(missing_ok=True)
    monkeypatch.setenv("COPILOT_ENV_FILE", str(env))
    client = TestClient(server_mod.app)
    try:
        r = client.post("/api/backend/byok", json={
            "base_url": "https://api.groq.com/openai/v1", "api_key": "gsk_secret", "model": "llama-3.3-70b"})
        assert r.status_code == 200
        b = r.json()["byok"]
        assert b["base_url"].endswith("/v1") and b["model"].startswith("llama") and b["has_key"] is True
        assert "api_key" not in b                              # 回應不含真實金鑰
        assert "OPENAI_API_KEY=gsk_secret" in env.read_text(encoding="utf-8")
    finally:
        env.unlink(missing_ok=True)


def test_backend_test_openai_probe(monkeypatch):
    monkeypatch.setattr(server_mod, "_backend_available", lambda name: True)
    monkeypatch.setattr(server_mod, "_probe_openai", lambda: "你好")
    client = TestClient(server_mod.app)
    r = client.post("/api/backend/test", json={"backend": "openai"})
    assert r.status_code == 200 and r.json()["ok"] is True


def test_history_approve_endpoint_marks_approved(monkeypatch):
    # 背景產生待審包後，POST /api/history/{id}/approve 應把它標記為已核可。
    _patch_agents(monkeypatch)
    client = TestClient(server_mod.app)
    d, _ = _run_bg(client, {"jd_text": "JD"})
    pid = d["package_id"]
    assert client.post(f"/api/history/{pid}/approve").json()["ok"] is True
    assert server_mod._history.get_package(pid)["approved"] == 1


def test_favicon_is_served():
    # 回歸：/favicon.svg 必須由後端提供（不在 /assets 底下），否則分頁圖示 404 沿用舊圖。
    client = TestClient(server_mod.app)
    r = client.get("/favicon.svg")
    assert r.status_code == 200
    assert "svg" in r.headers.get("content-type", "")
    # 瀏覽器會自動請求 /favicon.ico，也要回 svg 而非 404
    assert client.get("/favicon.ico").status_code == 200


def test_index_serves_html():
    client = TestClient(server_mod.app)
    r = client.get("/")
    assert r.status_code == 200
    assert "<html" in r.text.lower()
    assert "求職" in r.text  # 確認是我們的頁面而非佔位


def test_resume_evaluate_with_text(monkeypatch):
    from app.models import Profile, ResumeAssessment
    server_mod._memory.clear_memory()
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
    assert server_mod._memory.get_memory()["profile"] is None  # 解析履歷不應無提示跨 session 保存


def test_resume_evaluate_progress_sets_expectation(monkeypatch):
    from app.models import Profile, ResumeAssessment
    server_mod._memory.clear_memory()
    monkeypatch.setattr(server_mod, "structure_profile",
                        lambda text: Profile(name="王小明", summary="後端工程師", raw_text=text))
    monkeypatch.setattr(server_mod, "evaluate_resume",
                        lambda text, profile: ResumeAssessment(
                            overall_score=80, clarity_score=80, impact_score=80,
                            ats_keyword_score=80, localization_score=80,
                            completeness_score=80, summary="不錯"))
    client = TestClient(server_mod.app)
    r = client.post("/api/resume/evaluate", data={"resume_text": "我的履歷 Python"})
    events = _parse_sse(r.text)
    messages = [e["message"] for e in events if e["type"] == "progress"]

    assert any("可能需要" in message for message in messages)
    assert any("深度健檢" in message for message in messages)


def test_resume_evaluate_falls_back_when_llm_returns_bad_json(monkeypatch):
    from app.llm_errors import LLMResponseFormatError
    from app.models import Profile
    server_mod._memory.clear_memory()
    monkeypatch.setattr(server_mod, "structure_profile",
                        lambda text: Profile(name="王小明", summary="後端工程師",
                                             skills=["Python"], raw_text=text))

    def bad_json(text, profile):
        raise LLMResponseFormatError("API key 回覆不是合法 JSON", kind="json")

    monkeypatch.setattr(server_mod, "evaluate_resume", bad_json)
    client = TestClient(server_mod.app)
    r = client.post("/api/resume/evaluate",
                    data={"resume_text": "Python 後端工程師，API 延遲降低 30%"})
    events = _parse_sse(r.text)
    types = [e["type"] for e in events]

    assert "error" not in types
    assert "assessment" in types
    assert types[-1] == "done"
    assessment = next(e["data"] for e in events if e["type"] == "assessment")
    assert "保守備援" in assessment["summary"]
    assert assessment["issues"]


def test_resume_evaluate_falls_back_when_llm_times_out(monkeypatch):
    from app.models import Profile
    server_mod._memory.clear_memory()
    monkeypatch.setattr(server_mod, "structure_profile",
                        lambda text: Profile(name="Candidate", summary="Backend engineer",
                                             skills=["Python"], raw_text=text))

    def timeout(text, profile):
        raise RuntimeError("CLI timeout (>120 seconds)")

    monkeypatch.setattr(server_mod, "evaluate_resume", timeout)
    client = TestClient(server_mod.app)
    r = client.post("/api/resume/evaluate",
                    data={"resume_text": "Python backend engineer improved APIs by 30%"})
    events = _parse_sse(r.text)
    types = [e["type"] for e in events]

    assert "error" not in types
    assert "assessment" in types
    assert types[-1] == "done"
    assert any(e.get("step") == "fallback" for e in events if e["type"] == "progress")
    assessment = next(e["data"] for e in events if e["type"] == "assessment")
    assert assessment["issues"]


def test_resume_evaluate_auto_saves_check_history(monkeypatch):
    from app.models import Profile, ResumeAssessment, ResumeIssue
    from app.store import resume_checks
    resume_checks.delete_all_checks()
    server_mod._memory.clear_memory()
    monkeypatch.setattr(server_mod, "structure_profile",
                        lambda text: Profile(name="Alex Chen", summary="Backend engineer",
                                             skills=["FastAPI"], raw_text=text))
    monkeypatch.setattr(server_mod, "evaluate_resume",
                        lambda text, profile: ResumeAssessment(
                            overall_score=88, clarity_score=86, impact_score=82,
                            ats_keyword_score=90, localization_score=89,
                            completeness_score=87, summary="深度健檢完成",
                            strengths=["定位清楚"],
                            issues=[ResumeIssue(severity="low", area="量化成果",
                                                problem="可再補", fix="加入數字")],
                        ))
    client = TestClient(server_mod.app)
    r = client.post("/api/resume/evaluate", data={"resume_text": "Alex Chen FastAPI backend"})
    events = _parse_sse(r.text)

    assert [e["type"] for e in events][-1] == "done"
    rows = resume_checks.list_checks()
    row = next(r for r in rows if r["label"].startswith("Alex Chen"))
    assert row["overall_score"] == 88
    assert row["assessment_mode"] == "deep"
    detail = client.get(f"/api/resume/checks/{row['id']}").json()
    assert detail["profile"]["name"] == "Alex Chen"
    assert detail["assessment"]["summary"] == "深度健檢完成"


def test_memory_profile_requires_explicit_save_and_can_delete():
    server_mod._memory.clear_memory()
    client = TestClient(server_mod.app)

    r = client.put("/api/memory/profile", json={"profile": {"name": "王小明", "summary": "後端工程師"}})
    assert r.status_code == 200
    assert server_mod._memory.get_memory()["profile"]["name"] == "王小明"

    bad = client.put("/api/memory/profile", json={"profile": {"skills": ["Python"]}})
    assert bad.status_code == 400

    gone = client.delete("/api/memory/profile")
    assert gone.status_code == 200
    assert server_mod._memory.get_memory()["profile"] is None


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
    from app.models import JobMatch, JobPosting, Profile, SearchResult
    monkeypatch.setattr(server_mod, "structure_profile",
                        lambda text: Profile(name="王", summary="後端", raw_text=text))
    monkeypatch.setattr(server_mod, "derive_queries", lambda profile: ["AI 工程師"])
    monkeypatch.setattr(server_mod, "search_all",
                        lambda q, limit=10, pages=1, area=None: [SearchResult(source="104", jobs=[
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


def test_jobs_auto_passes_pages_to_search(monkeypatch):
    """前端傳的 pages 應下傳給 search_all；未帶時預設 2、超界夾在 1–5。"""
    from app.models import Profile, SearchResult
    monkeypatch.setattr(server_mod, "structure_profile",
                        lambda text: Profile(name="王", summary="後端", raw_text=text))
    monkeypatch.setattr(server_mod, "derive_queries", lambda profile: ["AI"])
    monkeypatch.setattr(server_mod, "rank_jobs", lambda profile, jobs, top_k=None: [])
    captured = {}

    def fake_search(q, limit=15, pages=1, area=None):
        captured["pages"] = pages
        return [SearchResult(source="104", jobs=[])]
    monkeypatch.setattr(server_mod, "search_all", fake_search)
    client = TestClient(server_mod.app)

    client.post("/api/jobs/auto", data={"resume_text": "x"})
    assert captured["pages"] == 2                       # 預設
    client.post("/api/jobs/auto", data={"resume_text": "x", "pages": "9"})
    assert captured["pages"] == 5                       # 上界夾住
    client.post("/api/jobs/auto", data={"resume_text": "x", "pages": "0"})
    assert captured["pages"] == 1                       # 下界夾住


def test_jobs_auto_region_filters_uniformly(monkeypatch):
    """選地區：104 收到 area 代碼（來源端篩）；非-104 來源的外地職缺由結果端 location 過濾掉。"""
    from app.models import JobMatch, JobPosting, Profile, SearchResult
    monkeypatch.setattr(server_mod, "structure_profile",
                        lambda text: Profile(name="王", summary="後端", raw_text=text))
    monkeypatch.setattr(server_mod, "derive_queries", lambda profile: ["AI"])
    captured = {}

    def fake_search(q, limit=15, pages=1, area=None):
        captured["area"] = area
        return [
            SearchResult(source="104", jobs=[  # 104：信任來源端 area，不再結果端過濾
                JobPosting(source="104", title="台北職缺", company="A", url="u104", location="台北市信義區")]),
            SearchResult(source="cake", jobs=[  # cake：外地者應被結果端濾掉
                JobPosting(source="cake", title="台北遠端", company="B", url="ucake1", location="台北市"),
                JobPosting(source="cake", title="台中現場", company="C", url="ucake2", location="台中市西屯區")]),
        ]
    monkeypatch.setattr(server_mod, "search_all", fake_search)
    monkeypatch.setattr(server_mod, "rank_jobs",
                        lambda profile, jobs, top_k=None: [JobMatch(job=j, fit_score=70) for j in jobs])
    client = TestClient(server_mod.app)
    r = client.post("/api/jobs/auto", data={"resume_text": "x", "region": "台北市"})
    events = _parse_sse(r.text)
    assert captured["area"] == ["6001001000"]          # 台北市的 104 代碼
    titles = {m["job"]["title"] for e in events if e["type"] == "ranked_batch" for m in e["data"]}
    assert titles == {"台北職缺", "台北遠端"}            # 台中現場（非-104 外地）被濾掉


def test_jobs_auto_filters_jobs_by_max_experience_before_ranking(monkeypatch):
    """選年資門檻：超過門檻的職缺不送進 AI 排序；未標示年資者保留避免誤殺。"""
    from app.models import JobMatch, JobPosting, Profile, SearchResult
    monkeypatch.setattr(server_mod, "structure_profile",
                        lambda text: Profile(name="王", summary="後端", raw_text=text))
    monkeypatch.setattr(server_mod, "derive_queries", lambda profile: ["Python"])
    ranked_titles = []

    def fake_search(q, limit=15, pages=1, area=None):
        return [SearchResult(source="104", jobs=[
            JobPosting(source="104", title="Junior", company="A", url="u1",
                       min_years=1, experience_text="1 年以上"),
            JobPosting(source="104", title="Senior", company="B", url="u2",
                       min_years=5, experience_text="5 年以上"),
            JobPosting(source="104", title="Unknown", company="C", url="u3"),
        ])]

    def fake_rank(profile, jobs, top_k=None):
        ranked_titles.extend(j.title for j in jobs)
        return [JobMatch(job=j, fit_score=70) for j in jobs]

    monkeypatch.setattr(server_mod, "search_all", fake_search)
    monkeypatch.setattr(server_mod, "rank_jobs", fake_rank)
    client = TestClient(server_mod.app)
    r = client.post("/api/jobs/auto", data={
        "resume_text": "Python 後端",
        "max_experience_years": "2",
    })
    events = _parse_sse(r.text)

    assert not any(e["type"] == "error" for e in events)
    assert ranked_titles == ["Junior", "Unknown"]
    titles = {m["job"]["title"] for e in events if e["type"] == "ranked_batch" for m in e["data"]}
    assert titles == {"Junior", "Unknown"}


def test_jobs_auto_filters_jobs_by_salary_before_ranking(monkeypatch):
    """選薪資範圍：明確不相交的職缺不送進 AI 排序；面議/未標示依 checkbox 決定。"""
    from app.models import JobMatch, JobPosting, Profile, SearchResult
    monkeypatch.setattr(server_mod, "structure_profile",
                        lambda text: Profile(name="王", summary="後端", raw_text=text))
    monkeypatch.setattr(server_mod, "derive_queries", lambda profile: ["Python"])
    ranked_titles = []

    def fake_search(q, limit=15, pages=1, area=None):
        return [SearchResult(source="104", jobs=[
            JobPosting(source="104", title="Too low", company="A", url="s1",
                       salary="月薪 NT$40,000–50,000"),
            JobPosting(source="104", title="Match", company="B", url="s2",
                       salary="月薪 NT$60,000–90,000"),
            JobPosting(source="cake", title="Too high", company="C", url="s3",
                       salary="年薪 TWD 1,500,000–2,100,000"),
            JobPosting(source="104", title="Negotiable", company="D", url="s4",
                       salary="面議"),
            JobPosting(source="yourator", title="Unknown", company="E", url="s5"),
        ])]

    def fake_rank(profile, jobs, top_k=None):
        ranked_titles.extend(j.title for j in jobs)
        return [JobMatch(job=j, fit_score=70) for j in jobs]

    monkeypatch.setattr(server_mod, "search_all", fake_search)
    monkeypatch.setattr(server_mod, "rank_jobs", fake_rank)
    client = TestClient(server_mod.app)
    r = client.post("/api/jobs/auto", data={
        "resume_text": "Python 後端",
        "salary_unit": "monthly",
        "min_salary": "60000",
        "max_salary": "90000",
        "include_unknown_salary": "false",
    })
    events = _parse_sse(r.text)

    assert not any(e["type"] == "error" for e in events)
    assert ranked_titles == ["Match"]
    titles = {m["job"]["title"] for e in events if e["type"] == "ranked_batch" for m in e["data"]}
    assert titles == {"Match"}


def test_pipeline_chat_resume_applies_update(monkeypatch):
    """履歷對話：AI 給修訂 → 端點回傳 reply + updated{summary,bullets}。"""
    from app.agents import refine as refine_mod
    from app.agents.refine import RefineResult
    monkeypatch.setattr(refine_mod, "refine_document",
                        lambda doc_type, current, messages, jd, profile: RefineResult(
                            reply="已幫你強化 LLM 經驗",
                            updated_summary="資深 LLM 工程師",
                            updated_bullets=["打造 RAG 系統", "多代理編排"]))
    client = TestClient(server_mod.app)
    r = client.post("/api/pipeline/chat", json={
        "doc_type": "resume", "current": "舊摘要", "jd_text": "LLM 工程師",
        "profile": {"name": "王", "summary": "後端"},
        "messages": [{"role": "user", "content": "強化 LLM 經驗"}],
    })
    assert r.status_code == 200
    d = r.json()
    assert d["reply"].startswith("已幫")
    assert d["updated"]["summary"] == "資深 LLM 工程師"
    assert d["updated"]["bullets"] == ["打造 RAG 系統", "多代理編排"]


def test_pipeline_chat_discussion_returns_no_update(monkeypatch):
    """純討論（無修訂）→ updated 為 None。"""
    from app.agents import refine as refine_mod
    from app.agents.refine import RefineResult
    monkeypatch.setattr(refine_mod, "refine_document",
                        lambda *a, **k: RefineResult(reply="可以考慮加上量化成果"))
    client = TestClient(server_mod.app)
    r = client.post("/api/pipeline/chat", json={
        "doc_type": "cover", "profile": {"name": "王", "summary": "後端"},
        "messages": [{"role": "user", "content": "這樣可以嗎"}],
    })
    assert r.status_code == 200
    assert r.json()["updated"] is None


def test_jobs_auto_lists_company_jobs_in_separate_event(monkeypatch):
    """指定公司名單時，公司開缺走獨立的 company_jobs 事件、與 AI 推薦分開排序。"""
    from app.models import JobMatch, JobPosting, Profile, SearchResult
    monkeypatch.setattr(server_mod, "structure_profile",
                        lambda text: Profile(name="王", summary="後端", raw_text=text))
    monkeypatch.setattr(server_mod, "derive_queries", lambda profile: ["AI 工程師"])
    monkeypatch.setattr(server_mod, "search_all",
                        lambda q, limit=15, pages=1, area=None: [SearchResult(source="104", jobs=[
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
    from app.models import JobMatch, JobPosting, Profile, SearchResult
    monkeypatch.setattr(server_mod, "structure_profile",
                        lambda text: Profile(name="王", summary="後端", raw_text=text))
    monkeypatch.setattr(server_mod, "derive_queries", lambda profile: ["AI 工程師"])
    monkeypatch.setattr(server_mod, "search_all",
                        lambda q, limit=15, pages=1, area=None: [SearchResult(source="104", jobs=[
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
