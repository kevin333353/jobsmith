"""Bounded queueing and anonymous source-result caching for public Web traffic."""
from __future__ import annotations

import os
import threading
import time
import uuid
from collections import OrderedDict, deque
from collections.abc import Callable, Hashable, Sequence
from dataclasses import dataclass
from typing import Literal

from app.models import SearchResult

CacheStatus = Literal["miss", "hit", "shared"]


def _bounded_env(name: str, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except ValueError:
        value = default
    return max(minimum, min(maximum, value))


def public_search_queue_capacity() -> int:
    return _bounded_env("JOBSMITH_PUBLIC_SEARCH_QUEUE", 12, 1, 100)


def public_preview_concurrency() -> int:
    return _bounded_env("JOBSMITH_PUBLIC_PREVIEW_CONCURRENCY", 2, 1, 8)


def public_search_wait_seconds() -> int:
    return _bounded_env("JOBSMITH_PUBLIC_SEARCH_WAIT_SECONDS", 90, 10, 300)


def public_search_cache_ttl_seconds() -> int:
    return _bounded_env("JOBSMITH_PUBLIC_SEARCH_CACHE_TTL", 15 * 60, 60, 60 * 60)


def public_search_cache_entries() -> int:
    return _bounded_env("JOBSMITH_PUBLIC_SEARCH_CACHE_ENTRIES", 64, 8, 256)


@dataclass(frozen=True)
class SearchQueueState:
    ticket_id: str
    accepted: bool
    acquired: bool
    position: int


class PublicSearchGate:
    """A small FIFO gate that prevents a traffic spike from exhausting the process."""

    def __init__(self, concurrency: int, max_queue: int):
        self.concurrency = max(1, concurrency)
        self.max_queue = max(0, max_queue)
        self._condition = threading.Condition()
        self._active: set[str] = set()
        self._waiting: deque[str] = deque()

    def register(self) -> SearchQueueState:
        ticket_id = uuid.uuid4().hex
        with self._condition:
            if len(self._active) < self.concurrency and not self._waiting:
                self._active.add(ticket_id)
                return SearchQueueState(ticket_id, True, True, 0)
            if len(self._waiting) >= self.max_queue:
                return SearchQueueState(ticket_id, False, False, 0)
            self._waiting.append(ticket_id)
            return SearchQueueState(ticket_id, True, False, len(self._waiting))

    def wait_for_turn(self, ticket_id: str, timeout: float = 2.0) -> SearchQueueState:
        """Wait briefly and report the current FIFO position without blocking forever."""
        with self._condition:
            if ticket_id in self._active:
                return SearchQueueState(ticket_id, True, True, 0)
            if ticket_id not in self._waiting:
                return SearchQueueState(ticket_id, False, False, 0)

            ready = (
                self._waiting[0] == ticket_id
                and len(self._active) < self.concurrency
            )
            if not ready:
                self._condition.wait(timeout=max(0.0, timeout))
                ready = (
                    bool(self._waiting)
                    and self._waiting[0] == ticket_id
                    and len(self._active) < self.concurrency
                )
            if ready:
                self._waiting.popleft()
                self._active.add(ticket_id)
                return SearchQueueState(ticket_id, True, True, 0)
            if ticket_id not in self._waiting:
                return SearchQueueState(ticket_id, False, False, 0)
            return SearchQueueState(
                ticket_id,
                True,
                False,
                list(self._waiting).index(ticket_id) + 1,
            )

    def release(self, ticket_id: str) -> None:
        with self._condition:
            removed = ticket_id in self._active
            self._active.discard(ticket_id)
            if ticket_id in self._waiting:
                self._waiting.remove(ticket_id)
                removed = True
            if removed:
                self._condition.notify_all()

    def snapshot(self) -> dict[str, int]:
        with self._condition:
            return {
                "concurrency": self.concurrency,
                "queue_capacity": self.max_queue,
                "active": len(self._active),
                "queued": len(self._waiting),
            }


@dataclass
class _CacheEntry:
    expires_at: float
    results: list[SearchResult]


@dataclass
class _InFlight:
    done: threading.Event
    error: BaseException | None = None


class SearchResultCache:
    """TTL/LRU cache with single-flight loading for non-personal job-board results."""

    def __init__(
        self,
        ttl_seconds: int,
        max_entries: int,
        *,
        clock: Callable[[], float] = time.monotonic,
        shared_wait_seconds: float = 60.0,
    ):
        self.ttl_seconds = max(1, ttl_seconds)
        self.max_entries = max(1, max_entries)
        self._clock = clock
        self.shared_wait_seconds = max(1.0, shared_wait_seconds)
        self._lock = threading.Lock()
        self._entries: OrderedDict[Hashable, _CacheEntry] = OrderedDict()
        self._inflight: dict[Hashable, _InFlight] = {}
        self._hits = 0
        self._misses = 0
        self._shared = 0

    @staticmethod
    def _clone(results: Sequence[SearchResult]) -> list[SearchResult]:
        return [result.model_copy(deep=True) for result in results]

    def _get_locked(self, key: Hashable, now: float) -> list[SearchResult] | None:
        entry = self._entries.get(key)
        if entry is None:
            return None
        if entry.expires_at <= now:
            self._entries.pop(key, None)
            return None
        self._entries.move_to_end(key)
        return self._clone(entry.results)

    def get_or_load(
        self,
        key: Hashable,
        loader: Callable[[], Sequence[SearchResult]],
    ) -> tuple[list[SearchResult], CacheStatus]:
        """Return one deep-copied result set while identical concurrent loads share work."""
        with self._lock:
            cached = self._get_locked(key, self._clock())
            if cached is not None:
                self._hits += 1
                return cached, "hit"
            flight = self._inflight.get(key)
            if flight is None:
                flight = _InFlight(done=threading.Event())
                self._inflight[key] = flight
                self._misses += 1
                leader = True
            else:
                self._shared += 1
                leader = False

        if not leader:
            if not flight.done.wait(timeout=self.shared_wait_seconds):
                raise TimeoutError("timed out waiting for a shared source search")
            if flight.error is not None:
                raise RuntimeError("shared source search failed") from flight.error
            with self._lock:
                cached = self._get_locked(key, self._clock())
                if cached is None:
                    raise RuntimeError("shared source search completed without a cache entry")
                return cached, "shared"

        try:
            loaded = self._clone(list(loader()))
            # Briefly cache complete source failures to avoid immediately hammering a blocked site.
            ttl = self.ttl_seconds if any(not result.blocked for result in loaded) else min(60, self.ttl_seconds)
            with self._lock:
                self._entries[key] = _CacheEntry(
                    expires_at=self._clock() + ttl,
                    results=self._clone(loaded),
                )
                self._entries.move_to_end(key)
                while len(self._entries) > self.max_entries:
                    self._entries.popitem(last=False)
            return loaded, "miss"
        except BaseException as exc:
            flight.error = exc
            raise
        finally:
            with self._lock:
                self._inflight.pop(key, None)
                flight.done.set()

    def stats(self) -> dict[str, int]:
        with self._lock:
            now = self._clock()
            expired = [key for key, entry in self._entries.items() if entry.expires_at <= now]
            for key in expired:
                self._entries.pop(key, None)
            return {
                "entries": len(self._entries),
                "inflight": len(self._inflight),
                "hits": self._hits,
                "misses": self._misses,
                "shared": self._shared,
                "ttl_seconds": self.ttl_seconds,
                "max_entries": self.max_entries,
            }


def source_search_cache_key(
    keywords: str,
    *,
    sources: Sequence[str] | None,
    limit: int,
    pages: int,
    area: Sequence[str] | None,
    work_modes: Sequence[str] | None,
    include_inferred: bool,
) -> tuple[object, ...]:
    """Normalize only public search criteria; resume/profile data never enters this key."""
    return (
        " ".join((keywords or "").casefold().split()),
        tuple(sorted(set(sources or ()))),
        int(limit),
        int(pages),
        tuple(sorted(set(area or ()))),
        tuple(sorted(set(work_modes or ()))),
        bool(include_inferred),
    )
