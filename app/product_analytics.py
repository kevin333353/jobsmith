"""Privacy-preserving, server-side product analytics for the public Web surface.

The browser never talks to PostHog directly. Jobsmith emits only a fixed event
schema, replaces its essential browser-session cookie with a daily HMAC, and
drops events when analytics is disabled or the bounded delivery queue is full.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import queue
import re
import threading
from collections.abc import Callable, Iterable, Mapping
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import requests

from app.public_web import env_flag

_ALLOWED_POSTHOG_HOSTS = frozenset(
    {
        "https://eu.i.posthog.com",
        "https://us.i.posthog.com",
    }
)
_PROJECT_KEY = re.compile(r"^phc_[A-Za-z0-9_-]{8,200}$")
_CAMPAIGN = re.compile(r"^[a-z0-9][a-z0-9._-]{0,39}$")
_EVENT_PREFIX = "jobsmith_web_"

_ENUM_VALUES = {
    "device": frozenset({"mobile", "tablet", "desktop", "unknown"}),
    "source": frozenset(
        {
            "direct",
            "threads",
            "github",
            "google",
            "facebook",
            "instagram",
            "x",
            "referral",
            "other",
        }
    ),
    "resume_input": frozenset({"pdf", "docx", "txt", "text", "profile", "unknown"}),
    "duration_bucket": frozenset(
        {
            "under_1s",
            "1_3s",
            "3_10s",
            "10_30s",
            "30_60s",
            "60s_plus",
        }
    ),
    "target_role_count_bucket": frozenset({"0", "1", "2_3"}),
    "result_count_bucket": frozenset({"0", "1_9", "10_49", "50_99", "100_plus"}),
    "source_count_bucket": frozenset({"0", "1", "2_3", "4_plus"}),
    "cache_status": frozenset({"none", "miss", "hit", "shared", "mixed"}),
    "failure_category": frozenset(
        {
            "busy",
            "unsupported_file",
            "too_large",
            "invalid_input",
            "parse_error",
            "queue_full",
            "queue_timeout",
            "cancelled",
            "backend_unavailable",
            "server_error",
            "interrupted",
        }
    ),
}
_BOOL_PROPERTIES = frozenset(
    {
        "has_region_filter",
        "has_work_mode_filter",
        "has_company_filter",
        "queued",
    }
)
_EVENT_PROPERTIES = {
    "web_opened": frozenset({"device", "source", "campaign"}),
    "resume_preview_completed": frozenset(
        {
            "device",
            "resume_input",
            "duration_bucket",
            "target_role_count_bucket",
        }
    ),
    "resume_preview_failed": frozenset(
        {
            "device",
            "resume_input",
            "duration_bucket",
            "failure_category",
        }
    ),
    "search_started": frozenset(
        {
            "device",
            "resume_input",
            "target_role_count_bucket",
            "has_region_filter",
            "has_work_mode_filter",
            "has_company_filter",
        }
    ),
    "queue_entered": frozenset({"device"}),
    "queue_full": frozenset({"device"}),
    "search_completed": frozenset(
        {
            "device",
            "duration_bucket",
            "result_count_bucket",
            "source_count_bucket",
            "cache_status",
            "queued",
        }
    ),
    "search_failed": frozenset(
        {
            "device",
            "duration_bucket",
            "failure_category",
            "cache_status",
            "queued",
        }
    ),
}


def normalize_campaign(value: object) -> str:
    """Return a bounded campaign slug, never an arbitrary URL/query value."""
    normalized = str(value or "").strip().casefold()
    return normalized if _CAMPAIGN.fullmatch(normalized) else "none"


def sanitize_event_properties(
    event: str,
    properties: Mapping[str, object] | None,
) -> dict[str, str | bool]:
    """Keep only the documented low-cardinality properties for an event."""
    allowed = _EVENT_PROPERTIES.get(event)
    if allowed is None:
        return {}
    incoming = properties or {}
    sanitized: dict[str, str | bool] = {}
    for name in allowed:
        if name not in incoming:
            continue
        value = incoming[name]
        if name == "campaign":
            sanitized[name] = normalize_campaign(value)
        elif name in _BOOL_PROPERTIES:
            if isinstance(value, bool):
                sanitized[name] = value
        elif name in _ENUM_VALUES:
            normalized = str(value or "").strip().casefold()
            if normalized in _ENUM_VALUES[name]:
                sanitized[name] = normalized
    return sanitized


def anonymous_daily_id(
    session_cookie: str,
    secret: str,
    *,
    day: date | None = None,
) -> str:
    """Derive an unlinkable-per-day identifier without exposing the cookie."""
    if not session_cookie or not secret:
        return ""
    current_day = day or datetime.now(timezone.utc).date()
    message = f"{current_day.isoformat()}:{session_cookie}".encode()
    digest = hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()
    return f"anon_{digest[:32]}"


def device_bucket(user_agent: str) -> str:
    value = (user_agent or "").casefold()
    if not value:
        return "unknown"
    if "ipad" in value or "tablet" in value:
        return "tablet"
    if any(token in value for token in ("iphone", "ipod", "android", "mobile", "windows phone")):
        return "mobile"
    return "desktop"


def resume_input_bucket(
    filename: str | None,
    *,
    has_text: bool = False,
    has_profile: bool = False,
) -> str:
    if has_profile:
        return "profile"
    if filename:
        suffix = Path(filename).suffix.casefold().lstrip(".")
        return suffix if suffix in {"pdf", "docx", "txt"} else "unknown"
    return "text" if has_text else "unknown"


def duration_bucket(seconds: float) -> str:
    value = max(0.0, float(seconds))
    if value < 1:
        return "under_1s"
    if value < 3:
        return "1_3s"
    if value < 10:
        return "3_10s"
    if value < 30:
        return "10_30s"
    if value < 60:
        return "30_60s"
    return "60s_plus"


def target_role_count_bucket(count: int) -> str:
    if count <= 0:
        return "0"
    if count == 1:
        return "1"
    return "2_3"


def result_count_bucket(count: int) -> str:
    if count <= 0:
        return "0"
    if count < 10:
        return "1_9"
    if count < 50:
        return "10_49"
    if count < 100:
        return "50_99"
    return "100_plus"


def source_count_bucket(count: int) -> str:
    if count <= 0:
        return "0"
    if count == 1:
        return "1"
    if count < 4:
        return "2_3"
    return "4_plus"


def combined_cache_status(statuses: Iterable[str]) -> str:
    normalized = {status for status in statuses if status in {"miss", "hit", "shared"}}
    if not normalized:
        return "none"
    if len(normalized) == 1:
        return normalized.pop()
    return "mixed"


def preview_failure_category(message: str) -> str:
    value = (message or "").casefold()
    if "只支援" in value or "unsupported" in value:
        return "unsupported_file"
    if "too large" in value or "過長" in value or "100,000" in value:
        return "too_large"
    if "解析" in value or "parse" in value:
        return "parse_error"
    return "invalid_input"


def build_capture_payload(
    *,
    project_key: str,
    event: str,
    anonymous_id: str,
    app_version: str,
    properties: Mapping[str, object] | None = None,
) -> dict[str, Any] | None:
    if event not in _EVENT_PROPERTIES or not anonymous_id:
        return None
    return {
        "api_key": project_key,
        "event": f"{_EVENT_PREFIX}{event}",
        "properties": {
            "distinct_id": anonymous_id,
            "$process_person_profile": False,
            "$geoip_disable": True,
            "app_version": app_version,
            "surface": "public_web",
            **sanitize_event_properties(event, properties),
        },
    }


class ProductAnalytics:
    """Bounded, best-effort PostHog delivery that never blocks product work."""

    def __init__(
        self,
        *,
        enabled: bool,
        project_key: str,
        host: str,
        secret: str,
        app_version: str,
        queue_size: int = 512,
        sender: Callable[[str, dict[str, Any]], None] | None = None,
    ):
        normalized_host = (host or "").strip().rstrip("/")
        valid_key = bool(_PROJECT_KEY.fullmatch((project_key or "").strip()))
        self.enabled = bool(
            enabled and valid_key and normalized_host in _ALLOWED_POSTHOG_HOSTS and secret
        )
        self._project_key = (project_key or "").strip()
        self._host = normalized_host
        self._secret = secret
        self._app_version = app_version
        self._queue: queue.Queue[dict[str, Any]] = queue.Queue(maxsize=max(1, queue_size))
        self._sender = sender or self._send
        self._worker_lock = threading.Lock()
        self._worker: threading.Thread | None = None

    @classmethod
    def from_env(
        cls,
        *,
        public_web: bool,
        secret: str,
        app_version: str,
    ) -> ProductAnalytics:
        return cls(
            enabled=(public_web and env_flag("JOBSMITH_PUBLIC_ANALYTICS", default=False)),
            project_key=os.getenv("JOBSMITH_POSTHOG_PROJECT_KEY", ""),
            host=os.getenv("JOBSMITH_POSTHOG_HOST", "https://eu.i.posthog.com"),
            secret=secret,
            app_version=app_version,
        )

    def capture(
        self,
        event: str,
        session_cookie: str,
        properties: Mapping[str, object] | None = None,
    ) -> bool:
        if not self.enabled:
            return False
        payload = build_capture_payload(
            project_key=self._project_key,
            event=event,
            anonymous_id=anonymous_daily_id(session_cookie, self._secret),
            app_version=self._app_version,
            properties=properties,
        )
        if payload is None:
            return False
        try:
            self._queue.put_nowait(payload)
        except queue.Full:
            return False
        self._ensure_worker()
        return True

    def _ensure_worker(self) -> None:
        with self._worker_lock:
            if self._worker is not None and self._worker.is_alive():
                return
            self._worker = threading.Thread(
                target=self._run,
                name="jobsmith-product-analytics",
                daemon=True,
            )
            self._worker.start()

    def _run(self) -> None:
        while True:
            payload = self._queue.get()
            try:
                self._sender(self._host, payload)
            except Exception:
                # Analytics must never break search, leak payloads into logs, or retry forever.
                pass
            finally:
                self._queue.task_done()

    @staticmethod
    def _send(host: str, payload: dict[str, Any]) -> None:
        response = requests.post(
            f"{host}/capture/",
            json=payload,
            timeout=(2, 3),
        )
        response.raise_for_status()
