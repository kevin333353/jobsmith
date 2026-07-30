import threading
import time

from app.models import JobPosting, SearchResult
from app.public_capacity import (
    PublicSearchGate,
    SearchResultCache,
    source_search_cache_key,
)


def _result(title: str = "護理師") -> SearchResult:
    return SearchResult(
        source="104",
        jobs=[
            JobPosting(
                source="104",
                title=title,
                company="合成醫院",
                url=f"https://example.test/jobs/{title}",
            ),
        ],
    )


def test_public_search_gate_is_bounded_and_fifo():
    gate = PublicSearchGate(concurrency=1, max_queue=2)

    first = gate.register()
    second = gate.register()
    third = gate.register()
    rejected = gate.register()

    assert first.acquired
    assert (second.position, third.position) == (1, 2)
    assert not rejected.accepted
    assert gate.snapshot() == {
        "concurrency": 1,
        "queue_capacity": 2,
        "active": 1,
        "queued": 2,
    }

    gate.release(first.ticket_id)
    assert gate.wait_for_turn(second.ticket_id, timeout=0).acquired
    assert gate.wait_for_turn(third.ticket_id, timeout=0).position == 1
    gate.release(second.ticket_id)
    assert gate.wait_for_turn(third.ticket_id, timeout=0).acquired


def test_public_search_gate_removes_cancelled_waiter():
    gate = PublicSearchGate(concurrency=1, max_queue=2)
    active = gate.register()
    cancelled = gate.register()
    next_ticket = gate.register()

    gate.release(cancelled.ticket_id)

    assert gate.wait_for_turn(next_ticket.ticket_id, timeout=0).position == 1
    gate.release(active.ticket_id)
    assert gate.wait_for_turn(next_ticket.ticket_id, timeout=0).acquired


def test_search_result_cache_hits_expire_and_return_deep_copies():
    now = [100.0]
    calls = {"count": 0}
    cache = SearchResultCache(
        ttl_seconds=10,
        max_entries=2,
        clock=lambda: now[0],
    )

    def load():
        calls["count"] += 1
        return [_result()]

    first, first_status = cache.get_or_load(("護理師",), load)
    first[0].jobs[0].title = "被呼叫端修改"
    second, second_status = cache.get_or_load(("護理師",), load)

    assert (first_status, second_status) == ("miss", "hit")
    assert second[0].jobs[0].title == "護理師"
    assert calls["count"] == 1

    now[0] += 11
    _, third_status = cache.get_or_load(("護理師",), load)
    assert third_status == "miss"
    assert calls["count"] == 2


def test_search_result_cache_single_flights_identical_concurrent_loads():
    cache = SearchResultCache(ttl_seconds=60, max_entries=8)
    loader_started = threading.Event()
    allow_loader = threading.Event()
    calls = {"count": 0}
    outcomes = []

    def load():
        calls["count"] += 1
        loader_started.set()
        assert allow_loader.wait(2)
        return [_result("產品經理")]

    def lookup():
        outcomes.append(cache.get_or_load(("產品經理",), load))

    leader = threading.Thread(target=lookup)
    follower = threading.Thread(target=lookup)
    leader.start()
    assert loader_started.wait(1)
    follower.start()
    deadline = time.monotonic() + 1
    while cache.stats()["shared"] < 1 and time.monotonic() < deadline:
        time.sleep(0.01)
    allow_loader.set()
    leader.join(2)
    follower.join(2)

    assert not leader.is_alive()
    assert not follower.is_alive()
    assert calls["count"] == 1
    assert sorted(status for _, status in outcomes) == ["miss", "shared"]
    assert all(results[0].jobs[0].title == "產品經理" for results, _ in outcomes)


def test_source_search_cache_key_contains_only_normalized_search_scope():
    first = source_search_cache_key(
        "  Registered   NURSE ",
        sources=["cake", "104", "104"],
        limit=15,
        pages=2,
        area=["6001001000", "6001000000"],
        work_modes=["hybrid", "remote"],
        include_inferred=False,
    )
    second = source_search_cache_key(
        "registered nurse",
        sources=["104", "cake"],
        limit=15,
        pages=2,
        area=["6001000000", "6001001000"],
        work_modes=["remote", "hybrid"],
        include_inferred=False,
    )

    assert first == second
    assert "resume" not in repr(first).casefold()
    assert "profile" not in repr(first).casefold()
