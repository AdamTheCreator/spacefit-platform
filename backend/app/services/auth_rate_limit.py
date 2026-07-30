"""In-memory auth rate limiting + progressive login lockout.

Follows the repo's existing sliding-window pattern (``_IPRateLimiter`` in
``app/api/sales.py``). Per-process memory — acceptable for a single uvicorn
worker; **swap for Redis when scaling horizontally**, otherwise each worker
enforces its own quota.

Eviction: ``allow`` / ``register_failure`` opportunistically purge expired
entries on every Nth call so attacker-supplied keys can't grow the dicts
without bound. A hard cap (``_MAX_BUCKETS``) prevents pathological growth
even under sustained attack.
"""

from __future__ import annotations

import threading
import time
from collections import deque

from app.core.config import settings

_MAX_BUCKETS = 10_000
_EVICT_EVERY = 64


class SlidingWindowLimiter:
    """Generic per-key sliding-window limiter (used for reset / resend)."""

    def __init__(self) -> None:
        self._buckets: dict[str, deque[float]] = {}
        self._lock = threading.Lock()
        self._call_count = 0

    def allow(self, key: str, limit: int, window_seconds: int) -> bool:
        now = time.monotonic()
        cutoff = now - window_seconds
        with self._lock:
            self._call_count += 1
            if self._call_count % _EVICT_EVERY == 0:
                self._evict(cutoff)
            bucket = self._buckets.setdefault(key, deque())
            while bucket and bucket[0] < cutoff:
                bucket.popleft()
            if len(bucket) >= limit:
                return False
            bucket.append(now)
            return True

    def reset(self, key: str) -> None:
        with self._lock:
            self._buckets.pop(key, None)

    def _evict(self, cutoff: float) -> None:
        """Remove buckets whose window has fully elapsed (all entries expired)."""
        stale = [k for k, b in self._buckets.items() if not b or b[-1] < cutoff]
        for k in stale:
            self._buckets.pop(k, None)
        # Hard cap: drop oldest keys if we somehow exceeded the limit.
        if len(self._buckets) > _MAX_BUCKETS:
            for k in list(self._buckets.keys())[: len(self._buckets) - _MAX_BUCKETS]:
                self._buckets.pop(k, None)


class LoginLockout:
    """Tracks failed logins per key and applies progressive lockout.

    A key is any stable identifier — we track both the normalized email and
    the client IP so neither an account nor a source host can be brute-forced.
    """

    def __init__(self) -> None:
        self._failures: dict[str, deque[float]] = {}
        self._locked_until: dict[str, float] = {}
        self._lockout_count: dict[str, int] = {}
        self._lock = threading.Lock()
        self._call_count = 0

    def retry_after(self, key: str) -> int:
        """Seconds remaining on an active lockout, or 0 if not locked."""
        now = time.monotonic()
        with self._lock:
            until = self._locked_until.get(key, 0.0)
            remaining = until - now
            return int(remaining) + 1 if remaining > 0 else 0

    def register_failure(self, key: str) -> int:
        """Record a failed attempt; return retry_after seconds if now locked."""
        now = time.monotonic()
        window = settings.auth_login_window_seconds
        cutoff = now - window
        with self._lock:
            self._call_count += 1
            if self._call_count % _EVICT_EVERY == 0:
                self._evict(now, cutoff)
            bucket = self._failures.setdefault(key, deque())
            while bucket and bucket[0] < cutoff:
                bucket.popleft()
            bucket.append(now)
            if len(bucket) >= settings.auth_login_max_attempts:
                count = self._lockout_count.get(key, 0) + 1
                self._lockout_count[key] = count
                base = settings.auth_login_lockout_seconds
                duration = min(
                    base * (2 ** (count - 1)),
                    settings.auth_login_lockout_max_seconds,
                )
                self._locked_until[key] = now + duration
                bucket.clear()
                return int(duration)
            return 0

    def reset(self, key: str) -> None:
        with self._lock:
            self._failures.pop(key, None)
            self._locked_until.pop(key, None)
            self._lockout_count.pop(key, None)

    def _evict(self, now: float, cutoff: float) -> None:
        """Remove entries whose lockout has expired and failure window has elapsed."""
        # Evict expired lockouts
        expired_locks = [k for k, u in self._locked_until.items() if u < now]
        for k in expired_locks:
            self._locked_until.pop(k, None)
            self._lockout_count.pop(k, None)
        # Evict stale failure buckets
        stale = [k for k, b in self._failures.items() if not b or b[-1] < cutoff]
        for k in stale:
            self._failures.pop(k, None)
        # Hard cap
        if len(self._failures) > _MAX_BUCKETS:
            for k in list(self._failures.keys())[: len(self._failures) - _MAX_BUCKETS]:
                self._failures.pop(k, None)


# Singletons (per-process).
login_lockout = LoginLockout()
reset_limiter = SlidingWindowLimiter()
