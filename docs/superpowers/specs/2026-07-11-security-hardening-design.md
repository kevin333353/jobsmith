# Jobsmith Security Hardening Design

## Scope

This change fixes the five confirmed review findings without changing Jobsmith's local-first product model:

1. Protect the loopback FastAPI server from DNS rebinding and cross-site API requests.
2. Restore TLS certificate verification for every job source.
3. Make foreground and background cancellation reach active CLI work.
4. Stop active runs before clearing personal data and prevent post-clear writes.
5. Freeze the selected AI backend for the lifetime of each background pipeline.

The work is split into independent components with regression tests at each boundary. No hosted service, login flow, or persisted application secret is introduced.

## Local API Boundary

The server owns one high-entropy, process-local session secret. It is generated with `secrets.token_urlsafe()` at startup and is never written to SQLite, `.env`, logs, or local storage.

`TrustedHostMiddleware` accepts only `127.0.0.1`, `localhost`, and the test-only host used by Starlette's in-process client. A custom middleware protects `/api/*` routes:

- Requests with an `Origin` header must originate from loopback HTTP(S).
- API requests require the process session cookie, compared with `secrets.compare_digest()`.
- `GET /api/session` is the only bootstrap exception. It issues the secret as an `HttpOnly`, `SameSite=Strict` session cookie.
- Authentication failures return a generic JSON `403` response and never reveal whether the host, origin, or cookie was wrong.

The production index response also sets the cookie, so bundled and `run.bat` users are authenticated before React starts. During Vite development, the frontend performs the bootstrap request before rendering. Existing `fetch()` calls then work unchanged because the browser automatically sends the same-origin cookie through the Vite proxy.

Tests use an `api_client()` helper that bootstraps the cookie. Dedicated security tests deliberately use a raw client to verify rejected Host, Origin, missing-cookie, and wrong-cookie requests.

## Job Source TLS

`app.sources.base.http_get()` always uses Requests' normal certificate verification. Callers can no longer pass `verify=False`, and the module no longer suppresses `InsecureRequestWarning` globally. LinkedIn, Yourator, and Cake treat certificate failures exactly like other source failures: the source is marked blocked and no unverified response is parsed or displayed.

Regression tests inject an `SSLError`, verify each source attempted a verified connection, and assert the source degrades to `blocked=True` without returning attacker-controlled jobs.

## Cancellation and Privacy Clearing

Every `_Run` owns a `TaskToken`. `_run_pipeline_bg()` executes the graph inside that token's context. `request_stop()` sets both the run flag and the token, allowing `app.llm_cli._run_process()` to terminate an active Claude or Codex subprocess instead of waiting for a graph node to finish.

API-backed model wrappers check cancellation before and after each synchronous provider call. A request already accepted by a remote provider cannot be recalled, but cancellation prevents every subsequent LLM node and prevents its result from being persisted.

The privacy-clear endpoint follows this order:

1. Snapshot active runs while holding `_RUNS_LOCK`.
2. Request cancellation and cancel queued futures.
3. Remove the runs from the public registry.
4. Delete memory, searches, resume checks, and packages.

The worker checks cancellation before every state update and final persistence. Therefore a worker that finishes concurrently after clearing cannot recreate or update deleted personal records. The endpoint returns success after cancellation has been signalled; it does not block the HTTP thread for a provider timeout.

## Backend Snapshot

`app.settings` exposes an immutable `BackendSnapshot` containing the selected backend and all provider/model fields that can be changed in the UI. A context manager makes accessors such as `current_backend()`, `byok_model()`, and `local_model_base_url()` read from the active snapshot.

`_Run` captures a snapshot at creation and `_run_pipeline_bg()` activates it for the whole graph. UI changes still update the global defaults and affect newly created work, but every node in an existing pipeline continues using the provider selected when that pipeline started.

No API keys are emitted in events, logs, history records, or the frontend.

## Error Handling and Compatibility

- Static assets and the index remain reachable without an API cookie; only API data/actions are protected.
- Invalid Host is rejected before application routing.
- Invalid Origin or session state returns JSON `403`, allowing the UI to show its existing generic request errors.
- Source TLS failures remain isolated to the failing source.
- Stop remains idempotent; stopped and cleared runs never become `done` later.
- CLI, browser, desktop, Vite development, Windows packaging, and macOS packaging continue using loopback networking only.

## Verification

The implementation is complete only when all of the following pass:

- New API boundary security tests.
- New TLS verification regression tests for LinkedIn, Yourator, and Cake.
- New active-subprocess cancellation and privacy-clear race tests.
- New backend snapshot concurrency test.
- Full `pytest` suite.
- `npm run lint` and `npm run build`.
- `pip check` and `npm audit --audit-level=high`.
- Manual smoke request proving an attacker-controlled Host cannot read `/api/memory`.

