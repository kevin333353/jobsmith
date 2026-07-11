import json
import threading
from types import SimpleNamespace

from app import server as server_mod
from app.models import Profile, ResumeAssessment
from tests.client import RawTestClient, TestClient


def test_api_rejects_attacker_host():
    client = RawTestClient(server_mod.app)
    r = client.get("/api/memory", headers={"Host": "attacker.example:8000"})

    assert r.status_code == 400


def test_api_requires_process_session_cookie():
    client = RawTestClient(server_mod.app)

    assert client.get("/api/memory").status_code == 403
    client.cookies.set("jobsmith_session", "wrong", path="/api")
    assert client.get("/api/memory").status_code == 403


def test_api_rejects_non_loopback_origin():
    client = RawTestClient(server_mod.app)
    client.get("/api/session")

    r = client.get(
        "/api/memory",
        headers={"Origin": "https://attacker.example"},
    )

    assert r.status_code == 403


def test_api_session_bootstrap_allows_loopback_client():
    client = RawTestClient(server_mod.app)

    bootstrap = client.get("/api/session")

    assert bootstrap.status_code == 200
    assert bootstrap.cookies.get("jobsmith_session")
    assert client.get("/api/memory").status_code == 200


def _parse_sse(text: str) -> list[dict]:
    events = []
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("data:"):
            events.append(json.loads(line[len("data:"):].strip()))
    return events


def test_run_body_profile_path_is_not_loaded_from_http_input():
    injected = server_mod.Path("_profile_path_escape_test.json")
    injected.write_text(
        json.dumps({"name": "Injected Profile", "summary": "Loaded from unsafe path"}),
        encoding="utf-8",
    )
    try:
        body = server_mod.RunBody(jd_text="JD", profile_path=str(injected.resolve()))
        profile = server_mod._resolve_profile(body)
        assert profile.name != "Injected Profile"
    finally:
        injected.unlink(missing_ok=True)


def test_post_backend_byok_rejects_env_newline(monkeypatch):
    env = server_mod.Path("_byok_server_injection_test.env")
    env.unlink(missing_ok=True)
    monkeypatch.setenv("COPILOT_ENV_FILE", str(env))
    client = TestClient(server_mod.app)
    try:
        r = client.post("/api/backend/byok", json={
            "base_url": "https://api.example/v1\nOPENAI_API_KEY=leaked",
            "api_key": "sk-secret",
            "model": "gpt-4o",
        })
        assert r.status_code == 400
        if env.exists():
            assert "OPENAI_API_KEY=leaked" not in env.read_text(encoding="utf-8")
    finally:
        env.unlink(missing_ok=True)


def test_resume_evaluate_rejects_oversized_upload(monkeypatch):
    called = {"structure": 0}

    def fake_structure(text):
        called["structure"] += 1
        return Profile(name="Tester", summary="Summary", raw_text=text)

    monkeypatch.setattr(server_mod, "structure_profile", fake_structure)
    monkeypatch.setattr(
        server_mod,
        "evaluate_resume",
        lambda text, profile: ResumeAssessment(
            overall_score=80,
            clarity_score=80,
            impact_score=80,
            ats_keyword_score=80,
            localization_score=80,
            completeness_score=80,
            summary="ok",
        ),
    )
    limit = getattr(server_mod, "_MAX_RESUME_UPLOAD_BYTES", 5_000_000)
    client = TestClient(server_mod.app)
    r = client.post(
        "/api/resume/evaluate",
        files={"file": ("resume.txt", b"x" * (limit + 1), "text/plain")},
    )
    assert r.status_code == 200
    events = _parse_sse(r.text)
    assert any(e["type"] == "error" and "too large" in e.get("message", "") for e in events)
    assert called["structure"] == 0


def test_privacy_clear_removes_saved_personal_data():
    server_mod._memory.save_profile({"name": "Private User", "raw_text": "resume text"})
    server_mod._memory.save_preferences({"tone": "direct"})
    server_mod._searches.save_search(
        "Private search",
        {"name": "Private User"},
        {"jobs": [{"title": "AI Engineer"}]},
    )
    server_mod._history.save_package({
        "jd_text": "private jd",
        "profile": {"name": "Private User"},
        "parsed_job": {"title": "AI Engineer", "company": "Acme"},
        "match_report": {"score": 80},
    })
    server_mod._resume_checks.save_check(
        "Private check",
        "resume.pdf",
        {"name": "Private User"},
        ResumeAssessment(
            overall_score=80,
            clarity_score=80,
            impact_score=80,
            ats_keyword_score=80,
            localization_score=80,
            completeness_score=80,
            summary="private",
        ).model_dump(),
    )

    client = TestClient(server_mod.app)
    r = client.delete("/api/privacy-data")

    assert r.status_code == 200
    assert r.json()["ok"] is True
    assert server_mod._memory.get_memory() == {"profile": None, "preferences": {}}
    assert server_mod._searches.list_searches() == []
    assert server_mod._resume_checks.list_checks() == []
    assert server_mod._history.list_packages() == []


def test_privacy_clear_cancels_active_runs_before_deleting(monkeypatch):
    run = server_mod._Run("privacy-run", 42)
    with server_mod._RUNS_LOCK:
        server_mod._RUNS[run.thread_id] = run

    for obj, name in (
        (server_mod._memory, "clear_memory"),
        (server_mod._searches, "delete_all_searches"),
        (server_mod._resume_checks, "delete_all_checks"),
        (server_mod._history, "delete_all_packages"),
    ):
        monkeypatch.setattr(obj, name, lambda: None)

    response = TestClient(server_mod.app).delete("/api/privacy-data")

    assert response.status_code == 200
    assert run.token.is_cancelled()
    assert run.thread_id not in server_mod._RUNS


def test_privacy_clear_prevents_worker_post_clear_write(monkeypatch):
    started = threading.Event()
    release = threading.Event()
    writes = []

    class BlockingGraph:
        def stream(self, initial, config, stream_mode):
            started.set()
            release.wait(2)
            yield {"parse": {}}

        def get_state(self, config):
            return SimpleNamespace(values={})

    for obj, name in (
        (server_mod._memory, "clear_memory"),
        (server_mod._searches, "delete_all_searches"),
        (server_mod._resume_checks, "delete_all_checks"),
        (server_mod._history, "delete_all_packages"),
    ):
        monkeypatch.setattr(obj, name, lambda: None)
    monkeypatch.setattr(
        server_mod._history,
        "update_package_result",
        lambda pid, final: writes.append((pid, final)),
    )
    monkeypatch.setattr(server_mod._history, "set_status", lambda *args: None)

    run = server_mod._Run("privacy-worker", 42)
    with server_mod._RUNS_LOCK:
        server_mod._RUNS[run.thread_id] = run
    worker = threading.Thread(
        target=server_mod._run_pipeline_bg,
        args=(run, {}, {}, BlockingGraph()),
    )
    worker.start()
    assert started.wait(1)

    response = TestClient(server_mod.app).delete("/api/privacy-data")
    release.set()
    worker.join(2)

    assert response.status_code == 200
    assert not worker.is_alive()
    assert writes == []


def test_privacy_clear_holds_run_lock_through_data_deletion(monkeypatch):
    lock_was_held = []

    def observe_lock():
        acquired = server_mod._RUNS_LOCK.acquire(blocking=False)
        lock_was_held.append(not acquired)
        if acquired:
            server_mod._RUNS_LOCK.release()

    monkeypatch.setattr(server_mod._memory, "clear_memory", observe_lock)
    monkeypatch.setattr(server_mod._searches, "delete_all_searches", lambda: None)
    monkeypatch.setattr(server_mod._resume_checks, "delete_all_checks", lambda: None)
    monkeypatch.setattr(server_mod._history, "delete_all_packages", lambda: None)

    response = TestClient(server_mod.app).delete("/api/privacy-data")

    assert response.status_code == 200
    assert lock_was_held == [True]


def test_run_creation_is_serialized_with_privacy_clear(monkeypatch):
    lock_was_held = []

    def create_package(*args, **kwargs):
        acquired = server_mod._RUNS_LOCK.acquire(blocking=False)
        lock_was_held.append(not acquired)
        if acquired:
            server_mod._RUNS_LOCK.release()
        return 123

    class FakeFuture:
        def cancel(self):
            return True

    monkeypatch.setattr(server_mod._history, "create_running_package", create_package)
    monkeypatch.setattr(server_mod, "_new_run_graph", lambda: object())
    monkeypatch.setattr(server_mod._RUN_EXECUTOR, "submit", lambda *args: FakeFuture())

    result = server_mod.run(server_mod.RunBody(
        jd_text="private jd",
        profile={"name": "Private User", "summary": "Engineer"},
    ))
    with server_mod._RUNS_LOCK:
        server_mod._RUNS.pop(result["thread_id"], None)

    assert lock_was_held == [True]


def test_diagnostics_returns_fixed_error_log_location():
    client = TestClient(server_mod.app)
    r = client.get("/api/diagnostics")

    assert r.status_code == 200
    data = r.json()
    assert data["error_log"].endswith("data\\error.log") or data["error_log"].endswith("data/error.log")
    assert data["log_dir"]


def test_open_log_folder_uses_fixed_error_log_parent(monkeypatch):
    opened = []
    monkeypatch.setattr(server_mod, "_open_folder", lambda path: opened.append(path))
    client = TestClient(server_mod.app)

    r = client.post("/api/diagnostics/open-log-folder")

    assert r.status_code == 200
    assert r.json()["ok"] is True
    assert opened == [server_mod._ERROR_LOG.parent]
