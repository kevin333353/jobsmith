"""HTTP boundary for local Jobsmith and its reduced public Web surface."""
from __future__ import annotations

import hashlib
import hmac
import secrets
import threading
import time
from collections import defaultdict, deque
from urllib.parse import urlparse

from starlette.datastructures import MutableHeaders
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.public_web import (
    PUBLIC_WEB,
    configured_public_hosts,
    is_public_api_request,
    public_cookie_secure,
)

API_COOKIE = "jobsmith_session"
_LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost"})
ALLOWED_HOSTS = tuple(dict.fromkeys((*_LOOPBACK_HOSTS, *configured_public_hosts())))
_PUBLIC_RATE_LIMITS = {
    "/api/jobs/auto": (8, 10 * 60),
    "/api/resume/preview": (30, 10 * 60),
}
_MAX_PUBLIC_REQUEST_BYTES = 6 * 1024 * 1024


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


def is_allowed_origin(origin: str, public_hosts: tuple[str, ...] = ()) -> bool:
    """Accept loopback origins, plus exact HTTPS hosts configured for public Web."""
    try:
        parsed = urlparse(origin)
    except ValueError:
        return False
    host = (parsed.hostname or "").rstrip(".").casefold()
    if host in _LOOPBACK_HOSTS:
        return parsed.scheme in {"http", "https"}
    return parsed.scheme == "https" and host in public_hosts


def new_signed_session_token(secret: str) -> str:
    """Create a stateless per-browser CSRF token for the public deployment."""
    nonce = secrets.token_urlsafe(24)
    signature = hmac.new(secret.encode(), nonce.encode(), hashlib.sha256).hexdigest()
    return f"{nonce}.{signature}"


def verify_signed_session_token(value: str, secret: str) -> bool:
    try:
        nonce, signature = value.rsplit(".", 1)
    except ValueError:
        return False
    if not nonce or len(signature) != 64:
        return False
    expected = hmac.new(secret.encode(), nonce.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(signature, expected)


def set_session_cookie(
    response: Response,
    token: str,
    *,
    public_web: bool = PUBLIC_WEB,
) -> Response:
    """Attach an HttpOnly API session without exposing the secret to JavaScript."""
    value = new_signed_session_token(token) if public_web else token
    response.set_cookie(
        API_COOKIE,
        value,
        httponly=True,
        samesite="strict",
        secure=public_cookie_secure() if public_web else False,
        path="/api",
    )
    return response


class LocalAPISecurityMiddleware:
    """Require same-origin cookie auth and reduce public Web to a strict endpoint allowlist."""

    def __init__(
        self,
        app,
        token: str,
        *,
        public_web: bool = PUBLIC_WEB,
        public_hosts: tuple[str, ...] | None = None,
    ):
        self.app = app
        self.token = token
        self.public_web = public_web
        self.public_hosts = tuple(public_hosts or configured_public_hosts())
        self._rate_lock = threading.Lock()
        self._request_times: dict[tuple[str, str], deque[float]] = defaultdict(deque)

    def _rate_limited(self, request: Request, path: str) -> bool:
        limit = _PUBLIC_RATE_LIMITS.get(path)
        if not self.public_web or request.method != "POST" or limit is None:
            return False
        max_requests, window_seconds = limit
        client_host = request.client.host if request.client else "unknown"
        key = (client_host, path)
        now = time.monotonic()
        with self._rate_lock:
            timestamps = self._request_times[key]
            while timestamps and timestamps[0] <= now - window_seconds:
                timestamps.popleft()
            if len(timestamps) >= max_requests:
                return True
            timestamps.append(now)
        return False

    async def __call__(self, scope, receive, send):
        path = scope.get("path", "")
        if scope.get("type") != "http" or not path.startswith("/api/"):
            return await self.app(scope, receive, send)
        method = scope.get("method", "GET")
        if self.public_web and not is_public_api_request(method, path):
            response = JSONResponse({"error": "not available in public Web mode"}, status_code=404)
            return await response(scope, receive, send)
        if path in {"/api/session", "/api/healthz"}:
            return await self.app(scope, receive, send)

        request = Request(scope)
        if self.public_web and request.method == "POST":
            try:
                content_length = int(request.headers.get("content-length", "0"))
            except ValueError:
                content_length = 0
            if content_length > _MAX_PUBLIC_REQUEST_BYTES:
                response = JSONResponse(
                    {"error": "上傳內容過大，履歷檔案上限為 5 MB。"},
                    status_code=413,
                )
                return await response(scope, receive, send)
        origin = request.headers.get("origin")
        cookie = request.cookies.get(API_COOKIE, "")
        origin_allowed = not origin or is_allowed_origin(origin, self.public_hosts)
        cookie_allowed = (
            verify_signed_session_token(cookie, self.token)
            if self.public_web
            else secrets.compare_digest(cookie, self.token)
        )
        allowed = origin_allowed and cookie_allowed
        if not allowed:
            response = JSONResponse({"error": "forbidden"}, status_code=403)
            return await response(scope, receive, send)
        if self._rate_limited(request, path):
            response = JSONResponse(
                {"error": "請稍候再試，公開測試版已達此裝置的使用頻率上限。"},
                status_code=429,
                headers={"Retry-After": "600"},
            )
            return await response(scope, receive, send)
        return await self.app(scope, receive, send)


class PublicSecurityHeadersMiddleware:
    """Attach browser hardening headers to every public page and API response."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope.get("type") != "http":
            return await self.app(scope, receive, send)

        async def send_with_headers(message):
            if message.get("type") == "http.response.start":
                headers = MutableHeaders(scope=message)
                headers["Content-Security-Policy"] = (
                    "default-src 'self'; "
                    "script-src 'self'; "
                    "style-src 'self' 'unsafe-inline'; "
                    "img-src 'self' data:; "
                    "font-src 'self'; "
                    "connect-src 'self'; "
                    "object-src 'none'; "
                    "base-uri 'self'; "
                    "form-action 'self'; "
                    "frame-ancestors 'none'; "
                    "upgrade-insecure-requests"
                )
                headers["Cross-Origin-Opener-Policy"] = "same-origin"
                headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
                headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
                headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
                headers["X-Content-Type-Options"] = "nosniff"
                headers["X-Frame-Options"] = "DENY"
            await send(message)

        return await self.app(scope, receive, send_with_headers)
