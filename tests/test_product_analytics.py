import json
import threading
from datetime import date

from app.product_analytics import (
    ProductAnalytics,
    anonymous_daily_id,
    build_capture_payload,
    combined_cache_status,
    device_bucket,
    duration_bucket,
    normalize_campaign,
    result_count_bucket,
    sanitize_event_properties,
)


def test_anonymous_id_is_stable_only_for_same_session_and_day():
    session = "signed-browser-session-with-secret-material"
    first = anonymous_daily_id(session, "process-secret", day=date(2026, 7, 30))
    same = anonymous_daily_id(session, "process-secret", day=date(2026, 7, 30))
    next_day = anonymous_daily_id(session, "process-secret", day=date(2026, 7, 31))
    other_session = anonymous_daily_id("other-session", "process-secret", day=date(2026, 7, 30))

    assert first == same
    assert first.startswith("anon_")
    assert first != next_day
    assert first != other_session
    assert session not in first


def test_event_schema_drops_unknown_fields_and_invalid_values():
    properties = sanitize_event_properties(
        "search_started",
        {
            "device": "MOBILE",
            "resume_input": "pdf",
            "target_role_count_bucket": "2_3",
            "has_region_filter": True,
            "has_work_mode_filter": False,
            "has_company_filter": "yes",
            "resume_text": "private resume contents",
            "target_roles": ["護理師"],
            "email": "person@example.com",
        },
    )

    assert properties == {
        "device": "mobile",
        "resume_input": "pdf",
        "target_role_count_bucket": "2_3",
        "has_region_filter": True,
        "has_work_mode_filter": False,
    }


def test_capture_payload_has_privacy_controls_and_no_raw_identifiers():
    raw_cookie = "raw-signed-session-cookie"
    raw_user_agent = "Mozilla/5.0 private browser string"
    payload = build_capture_payload(
        project_key="phc_project_key_12345678",
        event="web_opened",
        anonymous_id=anonymous_daily_id(
            raw_cookie,
            "process-secret",
            day=date(2026, 7, 30),
        ),
        app_version="0.1.8",
        properties={
            "device": "mobile",
            "source": "threads",
            "campaign": "threads_202607",
            "cookie": raw_cookie,
            "user_agent": raw_user_agent,
            "url": "https://example.test/?email=person@example.com",
        },
    )

    assert payload is not None
    assert payload["event"] == "jobsmith_web_web_opened"
    assert payload["properties"]["$process_person_profile"] is False
    assert payload["properties"]["$geoip_disable"] is True
    assert payload["properties"]["source"] == "threads"
    assert payload["properties"]["campaign"] == "threads_202607"
    serialized = json.dumps(payload, ensure_ascii=False)
    assert raw_cookie not in serialized
    assert raw_user_agent not in serialized
    assert "person@example.com" not in serialized


def test_campaign_and_metric_buckets_are_bounded():
    assert normalize_campaign(" Threads.Launch-2026 ") == "threads.launch-2026"
    assert normalize_campaign("person@example.com") == "none"
    assert normalize_campaign("a" * 41) == "none"
    assert duration_bucket(0.9) == "under_1s"
    assert duration_bucket(10) == "10_30s"
    assert result_count_bucket(0) == "0"
    assert result_count_bucket(49) == "10_49"
    assert result_count_bucket(100) == "100_plus"
    assert combined_cache_status([]) == "none"
    assert combined_cache_status(["hit", "hit"]) == "hit"
    assert combined_cache_status(["hit", "miss"]) == "mixed"


def test_device_bucket_never_returns_raw_user_agent():
    assert device_bucket("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0)") == "mobile"
    assert device_bucket("Mozilla/5.0 (iPad; CPU OS 17_0)") == "tablet"
    assert device_bucket("Mozilla/5.0 (Windows NT 10.0; Win64; x64)") == "desktop"
    assert device_bucket("") == "unknown"


def test_analytics_requires_public_flag_valid_key_and_fixed_host(monkeypatch):
    monkeypatch.setenv("JOBSMITH_PUBLIC_ANALYTICS", "1")
    monkeypatch.setenv("JOBSMITH_POSTHOG_PROJECT_KEY", "phc_project_key_12345678")
    monkeypatch.setenv("JOBSMITH_POSTHOG_HOST", "https://eu.i.posthog.com")

    enabled = ProductAnalytics.from_env(
        public_web=True,
        secret="process-secret",
        app_version="0.1.8",
    )
    desktop = ProductAnalytics.from_env(
        public_web=False,
        secret="process-secret",
        app_version="0.1.8",
    )
    monkeypatch.setenv("JOBSMITH_POSTHOG_HOST", "https://collector.example")
    untrusted_host = ProductAnalytics.from_env(
        public_web=True,
        secret="process-secret",
        app_version="0.1.8",
    )

    assert enabled.enabled is True
    assert desktop.enabled is False
    assert untrusted_host.enabled is False


def test_capture_is_best_effort_and_delivers_only_sanitized_payload():
    delivered = []
    delivered_event = threading.Event()

    def sender(host, payload):
        delivered.append((host, payload))
        delivered_event.set()

    analytics = ProductAnalytics(
        enabled=True,
        project_key="phc_project_key_12345678",
        host="https://eu.i.posthog.com",
        secret="process-secret",
        app_version="0.1.8",
        sender=sender,
    )

    accepted = analytics.capture(
        "search_completed",
        "raw-session-cookie",
        {
            "device": "desktop",
            "duration_bucket": "3_10s",
            "result_count_bucket": "10_49",
            "source_count_bucket": "2_3",
            "cache_status": "hit",
            "queued": False,
            "resume_text": "must not leave the process",
        },
    )

    assert accepted is True
    assert delivered_event.wait(timeout=1)
    host, payload = delivered[0]
    assert host == "https://eu.i.posthog.com"
    assert payload["properties"]["result_count_bucket"] == "10_49"
    assert "resume_text" not in payload["properties"]
    assert "raw-session-cookie" not in json.dumps(payload)
