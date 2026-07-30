"""Runtime policy for the accountless, no-AI public Web preview."""
from __future__ import annotations

import os
import re
from urllib.parse import urlparse

_TRUE_VALUES = frozenset({"1", "true", "yes", "on"})
_PUBLIC_EXACT_API = frozenset({
    ("GET", "/api/healthz"),
    ("GET", "/api/runtime"),
    ("GET", "/api/session"),
    ("POST", "/api/jobs/auto"),
    ("POST", "/api/resume/preview"),
})
_PUBLIC_TASK_STOP = re.compile(r"^/api/tasks/[A-Za-z0-9._:-]{1,160}/stop$")


def env_flag(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().casefold() in _TRUE_VALUES


PUBLIC_WEB = env_flag("JOBSMITH_PUBLIC_WEB")


def _hostname(value: str) -> str:
    """Normalize a hostname or URL from deployment configuration."""
    raw = (value or "").strip()
    if not raw:
        return ""
    parsed = urlparse(raw if "://" in raw else f"//{raw}")
    return (parsed.hostname or "").strip().rstrip(".").casefold()


def configured_public_hosts() -> tuple[str, ...]:
    """Return exact public hosts; Render injects its canonical hostname at runtime."""
    candidates = [
        *os.getenv("JOBSMITH_PUBLIC_HOSTS", "").split(","),
        os.getenv("JOBSMITH_PUBLIC_ORIGIN", ""),
        os.getenv("RENDER_EXTERNAL_HOSTNAME", ""),
    ]
    hosts: list[str] = []
    for candidate in candidates:
        host = _hostname(candidate)
        if host and host not in hosts:
            hosts.append(host)
    return tuple(hosts)


def is_public_api_request(method: str, path: str) -> bool:
    """Keep the public surface deliberately smaller than the desktop API."""
    normalized_method = (method or "GET").upper()
    if (normalized_method, path) in _PUBLIC_EXACT_API:
        return True
    return normalized_method == "POST" and bool(_PUBLIC_TASK_STOP.fullmatch(path))


def public_cookie_secure() -> bool:
    """HTTPS cookies are mandatory in public mode, with an explicit local-test escape hatch."""
    return PUBLIC_WEB and env_flag("JOBSMITH_PUBLIC_COOKIE_SECURE", default=True)


def public_search_concurrency() -> int:
    try:
        value = int(os.getenv("JOBSMITH_PUBLIC_SEARCH_CONCURRENCY", "3"))
    except ValueError:
        value = 3
    return max(1, min(8, value))
