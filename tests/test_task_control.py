import subprocess
import threading

import pytest

from app import server as server_mod
from app.models import Profile
from tests.client import TestClient


def _parse_sse(text: str) -> list[dict]:
    events = []
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("data:"):
            import json

            events.append(json.loads(line[len("data:"):].strip()))
    return events


def test_task_stop_endpoint_marks_task_cancelled():
    from app import task_control

    token = task_control.create_task("unit-stop")
    client = TestClient(server_mod.app)
    r = client.post("/api/tasks/unit-stop/stop")

    assert r.status_code == 200
    assert r.json()["status"] == "stopped"
    assert token.is_cancelled()
    task_control.finish_task("unit-stop")


def test_background_stop_cancels_run_token():
    run = server_mod._Run("cancel-run", 1)

    run.request_stop()

    assert run.token.is_cancelled()


def test_background_stop_terminates_active_cli_process(monkeypatch):
    import app.llm_cli as cli

    started = threading.Event()
    terminated = threading.Event()
    killed = threading.Event()

    class FakeProcess:
        returncode = 0
        stdin = None

        def communicate(self, timeout=None):
            started.set()
            if terminated.is_set() or killed.is_set():
                return "", ""
            raise subprocess.TimeoutExpired("fake-cli", timeout)

        def terminate(self):
            terminated.set()

        def wait(self, timeout=None):
            return 0

        def kill(self):
            killed.set()

    monkeypatch.setattr(cli.subprocess, "Popen", lambda *args, **kwargs: FakeProcess())
    monkeypatch.setattr(server_mod._history, "set_status", lambda *args: None)

    class CLIBlockingGraph:
        def stream(self, initial, config, stream_mode):
            cli._run_process(["fake-cli"], env={}, timeout=1)
            return iter(())

    run = server_mod._Run("active-cli-run", 1)
    worker = threading.Thread(
        target=server_mod._run_pipeline_bg,
        args=(run, {}, {}, CLIBlockingGraph()),
    )
    worker.start()
    assert started.wait(1)

    run.request_stop()
    worker.join(2)

    assert not worker.is_alive()
    assert terminated.is_set()
    assert not killed.is_set()


def test_resume_evaluate_stops_after_profile_phase(monkeypatch):
    from app import task_control

    task_id = "resume-stop-unit"

    def cancel_after_profile(text):
        task_control.request_stop(task_id)
        return Profile(name="王小明", summary="後端工程師", raw_text=text)

    def should_not_evaluate(text, profile):
        raise AssertionError("evaluate_resume should not run after cancellation")

    monkeypatch.setattr(server_mod, "structure_profile", cancel_after_profile)
    monkeypatch.setattr(server_mod, "evaluate_resume", should_not_evaluate)

    client = TestClient(server_mod.app)
    r = client.post("/api/resume/evaluate", data={"resume_text": "履歷 Python", "task_id": task_id})
    events = _parse_sse(r.text)
    types = [e["type"] for e in events]

    assert "stopped" in types
    assert "assessment" not in types
    assert types[-1] == "stopped"


def test_jobs_auto_stops_after_profile_phase(monkeypatch):
    from app import task_control

    task_id = "jobs-stop-unit"

    def cancel_after_profile(text):
        task_control.request_stop(task_id)
        return Profile(name="王小明", summary="後端工程師", raw_text=text)

    def should_not_search(profile):
        raise AssertionError("derive_queries should not run after cancellation")

    monkeypatch.setattr(server_mod, "structure_profile", cancel_after_profile)
    monkeypatch.setattr(server_mod, "derive_queries", should_not_search)

    client = TestClient(server_mod.app)
    r = client.post("/api/jobs/auto", data={"resume_text": "履歷 Python", "task_id": task_id})
    events = _parse_sse(r.text)
    types = [e["type"] for e in events]

    assert "stopped" in types
    assert "queries" not in types
    assert types[-1] == "stopped"


def test_run_claude_does_not_spawn_when_task_cancelled(monkeypatch):
    import app.llm_cli as cli
    from app import task_control

    token = task_control.create_task("cli-cancelled")
    token.cancel()
    monkeypatch.setattr(cli.shutil, "which", lambda name: "claude")

    def fail_spawn(*args, **kwargs):
        raise AssertionError("subprocess should not spawn when task is cancelled")

    monkeypatch.setattr(cli.subprocess, "Popen", fail_spawn)

    with task_control.task_context(token), pytest.raises(task_control.TaskCancelled):
        cli._run_claude("hi", "haiku")

    task_control.finish_task("cli-cancelled")


def test_backend_test_can_be_stopped(monkeypatch):
    from app import task_control

    def cancelled_probe():
        task_control.check_cancelled()
        return "1"

    token = task_control.create_task("backend-test-stop")
    token.cancel()
    monkeypatch.setattr(server_mod, "_probe_claude", cancelled_probe)

    client = TestClient(server_mod.app)
    r = client.post("/api/backend/test", json={"backend": "claude_cli", "task_id": "backend-test-stop"})

    assert r.status_code == 200
    assert r.json()["ok"] is False
    assert "已停止" in r.json()["message"]
    task_control.finish_task("backend-test-stop")
