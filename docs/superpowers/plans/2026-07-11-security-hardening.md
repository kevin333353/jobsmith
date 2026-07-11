# Jobsmith Security Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix all five confirmed security and lifecycle findings while preserving Jobsmith's loopback-only, local-first workflow.

**Architecture:** Add a process-local cookie session and strict loopback host/origin middleware around the FastAPI API; restore verified HTTPS for all sources; propagate cancellation and an immutable backend snapshot through each background graph run. Each subsystem receives a regression test before production code changes.

**Tech Stack:** Python 3.11+, FastAPI/Starlette, React 19, TypeScript 6, pytest, Requests, LangGraph, ContextVar.

## Global Constraints

- The session secret must never be persisted or emitted to logs, API JSON, local storage, events, or SQLite.
- Static assets and `/` remain public; protected `/api/*` routes return generic JSON `403` on authentication failure.
- Only loopback hosts and origins are accepted.
- Every external job-source request uses TLS certificate verification.
- A stopped or privacy-cleared run must never later persist a completed package.
- A background pipeline uses one immutable backend configuration from start to finish.
- Existing CLI, desktop, browser, Vite, Windows, and macOS entry points remain supported.

---

### Task 1: Protect the loopback API with Host, Origin, and session-cookie checks

**Files:**
- Create: `app/security.py`
- Create: `tests/client.py`
- Modify: `app/server.py`
- Modify: `frontend/src/main.tsx`
- Modify: `tests/test_security_regressions.py`
- Modify: `tests/test_server.py`
- Modify: `tests/test_task_control.py`

**Interfaces:**
- Produces: `LocalAPISecurityMiddleware(app, token: str)`, `new_api_token() -> str`, `set_session_cookie(response, token) -> Response`, and `tests.client.TestClient`.
- Consumes: Starlette `Headers`, `Request`, `JSONResponse`, and `TrustedHostMiddleware`.

- [ ] **Step 1: Write failing API-boundary tests**

Add raw-client tests that prove an attacker Host, attacker Origin, missing cookie, and wrong cookie cannot read `/api/memory`, while a bootstrapped client can:

```python
def test_api_rejects_attacker_host():
    client = RawTestClient(server_mod.app)
    r = client.get("/api/memory", headers={"Host": "attacker.example:8000"})
    assert r.status_code == 400


def test_api_requires_process_session_cookie():
    client = RawTestClient(server_mod.app)
    assert client.get("/api/memory").status_code == 403
    assert client.get("/api/memory", cookies={"jobsmith_session": "wrong"}).status_code == 403


def test_api_rejects_non_loopback_origin():
    client = RawTestClient(server_mod.app)
    client.get("/api/session")
    r = client.get("/api/memory", headers={"Origin": "https://attacker.example"})
    assert r.status_code == 403


def test_api_session_bootstrap_allows_loopback_client():
    client = RawTestClient(server_mod.app)
    bootstrap = client.get("/api/session")
    assert bootstrap.status_code == 200
    assert bootstrap.cookies.get("jobsmith_session")
    assert client.get("/api/memory").status_code == 200
```

- [ ] **Step 2: Run the new tests and verify RED**

Run: `D:\jobsmith\.venv\Scripts\python.exe -m pytest tests/test_security_regressions.py -k "attacker_host or process_session or non_loopback_origin or session_bootstrap" -v`

Expected: FAIL because arbitrary Host and unauthenticated API requests currently return `200`, and `/api/session` does not exist.

- [ ] **Step 3: Implement the security module and server bootstrap**

Implement a pure ASGI middleware with a constant-time cookie comparison:

```python
API_COOKIE = "jobsmith_session"
ALLOWED_HOSTS = ("127.0.0.1", "localhost", "testserver")


def new_api_token() -> str:
    return secrets.token_urlsafe(32)


def is_loopback_origin(origin: str) -> bool:
    parsed = urlparse(origin)
    return parsed.scheme in {"http", "https"} and parsed.hostname in {"127.0.0.1", "localhost"}


class LocalAPISecurityMiddleware:
    def __init__(self, app, token: str):
        self.app = app
        self.token = token

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or not scope.get("path", "").startswith("/api/"):
            return await self.app(scope, receive, send)
        if scope["path"] == "/api/session":
            return await self.app(scope, receive, send)
        request = Request(scope)
        origin = request.headers.get("origin")
        cookie = request.cookies.get(API_COOKIE, "")
        if (origin and not is_loopback_origin(origin)) or not secrets.compare_digest(cookie, self.token):
            return await JSONResponse({"error": "forbidden"}, status_code=403)(scope, receive, send)
        return await self.app(scope, receive, send)
```

Register `TrustedHostMiddleware` as the outer middleware, add `GET /api/session`, and set the same `HttpOnly`, `SameSite=Strict`, `Path=/api` cookie on the production index response.

- [ ] **Step 4: Add the authenticated test client and update existing tests**

Create a subclass that bootstraps once after construction:

```python
from fastapi.testclient import TestClient as RawTestClient


class TestClient(RawTestClient):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        response = self.get("/api/session")
        assert response.status_code == 200
```

Change the three existing test modules to import `TestClient` from `tests.client`; security-negative tests import `RawTestClient`.

- [ ] **Step 5: Bootstrap the Vite frontend before React renders**

Wrap `createRoot(...).render(...)` in an async start function:

```typescript
async function start() {
  const response = await fetch("/api/session", { credentials: "same-origin" })
  if (!response.ok) throw new Error("Unable to establish local API session")
  createRoot(document.getElementById("root")!).render(/* existing StrictMode tree */)
}

void start()
```

- [ ] **Step 6: Verify GREEN and commit**

Run:

```powershell
D:\jobsmith\.venv\Scripts\python.exe -m pytest tests/test_security_regressions.py tests/test_server.py tests/test_task_control.py -q
npm run lint
npm run build
```

Expected: all selected Python tests pass; ESLint and Vite build exit `0`.

Commit: `git commit -am "security: protect local API session"` plus the two new files.

### Task 2: Restore TLS verification for all job sources

**Files:**
- Modify: `app/sources/base.py`
- Modify: `app/sources/source_linkedin.py`
- Modify: `app/sources/source_yourator.py`
- Modify: `app/sources/source_cake.py`
- Modify: `tests/test_sources.py`

**Interfaces:**
- Produces: `http_get(url: str, *, referer: str | None = None, timeout: int = TIMEOUT)` with certificate verification always enabled.
- Consumes: Requests' default CA validation and existing `SearchResult(blocked=True)` fallback behavior.

- [ ] **Step 1: Write the failing verified-transport regression test**

```python
@pytest.mark.parametrize("source", [source_linkedin, source_yourator, source_cake])
def test_public_sources_never_disable_tls_verification(monkeypatch, source):
    calls = []

    def fail_tls(*args, **kwargs):
        calls.append(kwargs)
        raise requests.exceptions.SSLError("untrusted certificate")

    monkeypatch.setattr(source, "http_get", fail_tls)
    result = source.search("python", limit=1, pages=1)
    assert calls and all("verify" not in kwargs for kwargs in calls)
    assert result.blocked is True
    assert result.jobs == []
```

- [ ] **Step 2: Run the test and verify RED**

Run: `D:\jobsmith\.venv\Scripts\python.exe -m pytest tests/test_sources.py::test_public_sources_never_disable_tls_verification -v`

Expected: FAIL because each source passes `verify=False`.

- [ ] **Step 3: Remove the insecure option and warning suppression**

Delete the `urllib3` import and `disable_warnings()` call, remove `verify` from `http_get()`, and remove every `verify=False` call and comment. Keep existing exception-to-blocked behavior.

- [ ] **Step 4: Verify GREEN and commit**

Run: `D:\jobsmith\.venv\Scripts\python.exe -m pytest tests/test_sources.py tests/test_search.py -q`

Expected: all selected tests pass.

Commit: `git commit -am "security: enforce TLS for job sources"`.

### Task 3: Freeze backend settings for each background pipeline

**Files:**
- Modify: `app/settings.py`
- Modify: `app/server.py`
- Modify: `tests/test_llm_backend.py`
- Modify: `tests/test_server.py`

**Interfaces:**
- Produces: immutable `BackendSnapshot`, `capture_backend_snapshot() -> BackendSnapshot`, and `backend_context(snapshot)`.
- Consumes: existing settings accessors; no agent signatures change.

- [ ] **Step 1: Write failing snapshot tests**

```python
def test_backend_snapshot_is_stable_while_global_selection_changes():
    settings.set_backend("claude_cli")
    snapshot = settings.capture_backend_snapshot()
    settings.set_backend("codex_cli")
    with settings.backend_context(snapshot):
        assert settings.current_backend() == "claude_cli"
    assert settings.current_backend() == "codex_cli"


def test_background_run_captures_backend_at_creation(monkeypatch):
    settings.set_backend("claude_cli")
    run = server_mod._Run("snapshot-run", 1)
    settings.set_backend("codex_cli")
    assert run.backend_snapshot.backend == "claude_cli"
```

- [ ] **Step 2: Run tests and verify RED**

Run: `D:\jobsmith\.venv\Scripts\python.exe -m pytest tests/test_llm_backend.py tests/test_server.py -k "snapshot" -v`

Expected: FAIL because snapshot interfaces and `_Run.backend_snapshot` do not exist.

- [ ] **Step 3: Implement the immutable snapshot and context accessors**

Create a frozen dataclass with explicit fields for backend, both CLI model choices, BYOK base URL/key/model, and local provider/base URL/key/model. Store the active value in `ContextVar[BackendSnapshot | None]`. Update every accessor to prefer the context snapshot and leave setters modifying only global defaults.

```python
@dataclass(frozen=True)
class BackendSnapshot:
    backend: str
    claude_cli_model: str
    codex_cli_model: str
    byok_base_url: str
    byok_api_key: str
    byok_model: str
    local_provider: str
    local_base_url: str
    local_api_key: str
    local_model: str
```

- [ ] **Step 4: Capture and activate the snapshot in background runs**

Set `self.backend_snapshot = settings.capture_backend_snapshot()` in `_Run.__init__()` and wrap the entire graph execution in `with settings.backend_context(run.backend_snapshot):`.

- [ ] **Step 5: Verify GREEN and commit**

Run: `D:\jobsmith\.venv\Scripts\python.exe -m pytest tests/test_llm_backend.py tests/test_server.py -q`

Expected: all selected tests pass.

Commit: `git commit -am "fix: freeze backend per pipeline"`.

### Task 4: Propagate cancellation and make privacy clearing race-safe

**Files:**
- Modify: `app/server.py`
- Modify: `app/graph.py`
- Modify: `app/llm.py`
- Modify: `tests/test_task_control.py`
- Modify: `tests/test_security_regressions.py`
- Modify: `tests/test_server.py`

**Interfaces:**
- Produces: `_Run.token: TaskToken`; `request_stop()` cancels both the run and token.
- Consumes: `task_control.task_context()`, `settings.backend_context()`, and existing `_run_process()` cancellation polling.

- [ ] **Step 1: Write failing active-run and privacy race tests**

Add a blocking fake graph that waits until cancellation is visible:

```python
def test_background_stop_cancels_run_token():
    run = server_mod._Run("cancel-run", 1)
    run.request_stop()
    assert run.token.is_cancelled()


def test_privacy_clear_cancels_active_runs_before_deleting(monkeypatch):
    run = server_mod._Run("privacy-run", 42)
    with server_mod._RUNS_LOCK:
        server_mod._RUNS[run.thread_id] = run
    client = TestClient(server_mod.app)
    response = client.delete("/api/privacy-data")
    assert response.status_code == 200
    assert run.token.is_cancelled()
    assert run.thread_id not in server_mod._RUNS
```

Add a worker regression test whose fake graph returns after clear and assert `update_package_result()` was never called.

- [ ] **Step 2: Run tests and verify RED**

Run: `D:\jobsmith\.venv\Scripts\python.exe -m pytest tests/test_task_control.py tests/test_security_regressions.py tests/test_server.py -k "background_stop or privacy_clear_cancels or post_clear" -v`

Expected: FAIL because `_Run` has no token and privacy clear only clears the registry.

- [ ] **Step 3: Wire TaskToken through background execution**

Create a token in `_Run`, cancel it in `request_stop()`, and execute graph streaming inside both contexts:

```python
with settings.backend_context(run.backend_snapshot), task_control.task_context(run.token):
    run.token.check()
    for chunk in graph.stream(initial, config, stream_mode="updates"):
        run.token.check()
        # existing event handling
```

Finish the token in `_run_pipeline_bg()`'s `finally` block. In `graph._safe()`, re-raise `TaskCancelled` instead of converting it to an artifact fallback.

- [ ] **Step 4: Add cancellation checks to API model wrappers**

Call `task_control.check_cancelled()` immediately before and after synchronous provider `.invoke()` calls in `_FriendlyStructured` and `_FriendlyStructuredChat`. Do not normalize `TaskCancelled` into a provider-format error.

- [ ] **Step 5: Cancel all runs before deleting personal data**

Snapshot and remove runs under `_RUNS_LOCK`, then call `request_stop()` and `future.cancel()` for each run before clearing memory and database tables. Keep worker-side cancellation checks immediately before final persistence.

- [ ] **Step 6: Verify GREEN and commit**

Run: `D:\jobsmith\.venv\Scripts\python.exe -m pytest tests/test_task_control.py tests/test_security_regressions.py tests/test_server.py tests/test_graph.py -q`

Expected: all selected tests pass; stopped and cleared runs never persist a done package.

Commit: `git commit -am "fix: cancel active runs before cleanup"`.

### Task 5: Full verification and security smoke tests

**Files:**
- Modify only if verification exposes a regression.

**Interfaces:**
- Consumes all prior tasks.
- Produces a clean, reviewable branch with evidence for every design requirement.

- [ ] **Step 1: Run the complete automated suite**

```powershell
D:\jobsmith\.venv\Scripts\python.exe -m pytest -q
npm run lint
npm run build
D:\jobsmith\.venv\Scripts\python.exe -m pip check
npm audit --audit-level=high
```

Expected: all commands exit `0`; live tests remain deselected by project configuration.

- [ ] **Step 2: Run focused attacker-host and cancellation smoke tests**

Use `RawTestClient` to save an in-memory private profile, request `/api/memory` with `Host: attacker.example:8000`, and assert the response is rejected without containing the profile. Start a fake blocking background run, stop it through the API, and assert its token is cancelled and no final package update occurs.

- [ ] **Step 3: Inspect secrets and insecure transport patterns**

Run:

```powershell
rg -n "verify=False|disable_warnings|jobsmith_session|api_token|BackendSnapshot" app frontend/src tests
git diff origin/master...HEAD --check
git status --short --branch
```

Expected: no insecure TLS patterns; session token references contain no logging or persistence; diff check is clean.

- [ ] **Step 4: Review the complete diff and commit any verification-only correction**

Review: `git diff origin/master...HEAD -- app frontend/src tests docs/superpowers`

If a verification correction was required, commit it with `git commit -am "test: close security regression gaps"`. Otherwise leave the prior focused commits unchanged.

