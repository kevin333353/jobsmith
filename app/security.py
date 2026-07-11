"""Loopback-only HTTP boundary for the local Jobsmith API."""
from __future__ import annotations

import secrets
from urllib.parse import urlparse

from starlette.requests import Request
from starlette.responses import JSONResponse, Response

API_COOKIE = "jobsmith_session"
ALLOWED_HOSTS = ("127.0.0.1", "localhost")
_LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost"})


def new_api_token() -> str:
    """Return a high-entropy process-local secret suitable for cookie auth."""
    return secrets.token_urlsafe(32)


def is_loopback_origin(origin: str) -> bool:
    """Accept browser origins served from Jobsmith's loopback HTTP endpoint only."""
    try:
        parsed = urlparse(origin)
    except ValueError:
        return False
    return parsed.scheme in {"http", "https"} and parsed.hostname in _LOOPBACK_HOSTS


def set_session_cookie(response: Response, token: str) -> Response:
    """Attach the process-local API session without exposing it to JavaScript."""
    response.set_cookie(
        API_COOKIE,
        token,
        httponly=True,
        samesite="strict",
        secure=False,  # Jobsmith intentionally serves HTTP on loopback.
        path="/api",
    )
    return response


class LocalAPISecurityMiddleware:
    """Require a loopback Origin (when present) and the process session cookie."""

    def __init__(self, app, token: str):
        self.app = app
        self.token = token

    async def __call__(self, scope, receive, send):
        path = scope.get("path", "")
        if scope.get("type") != "http" or not path.startswith("/api/"):
            return await self.app(scope, receive, send)
        if path == "/api/session":
            return await self.app(scope, receive, send)

        request = Request(scope)
        origin = request.headers.get("origin")
        cookie = request.cookies.get(API_COOKIE, "")
        allowed = (not origin or is_loopback_origin(origin)) and secrets.compare_digest(
            cookie,
            self.token,
        )
        if not allowed:
            response = JSONResponse({"error": "forbidden"}, status_code=403)
            return await response(scope, receive, send)
        return await self.app(scope, receive, send)
