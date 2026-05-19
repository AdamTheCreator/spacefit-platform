"""In-memory observability for specialist LLM calls.

Tracks per-specialist counters (call count, success/failure, token totals,
elapsed time, BYOK split) so an admin can see at a glance whether one
specialist is burning more budget than the rest, which model alias is
actually being routed to it, and whether the streaming path is failing
silently.

Single-process only. When we scale to multiple workers, swap the
backing dict for Redis/Postgres without changing the call sites.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any


@dataclass
class _SpecialistCounters:
    name: str
    calls: int = 0
    successes: int = 0
    failures: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    total_elapsed_ms: int = 0
    byok_calls: int = 0
    last_called_at: float | None = None
    last_model: str | None = None
    last_error: str | None = None
    # Per-model count so we can spot a misrouted alias.
    models_used: dict[str, int] = field(default_factory=lambda: defaultdict(int))


class SpecialistMetrics:
    """Thread-safe (within a process) counters store."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._counters: dict[str, _SpecialistCounters] = {}
        self._started_at = time.time()

    def record(
        self,
        *,
        name: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        elapsed_ms: int,
        success: bool,
        is_byok: bool,
        error: str | None = None,
    ) -> None:
        with self._lock:
            counters = self._counters.setdefault(name, _SpecialistCounters(name=name))
            counters.calls += 1
            if success:
                counters.successes += 1
            else:
                counters.failures += 1
                counters.last_error = error
            counters.input_tokens += max(0, input_tokens)
            counters.output_tokens += max(0, output_tokens)
            counters.total_elapsed_ms += max(0, elapsed_ms)
            counters.last_called_at = time.time()
            counters.last_model = model
            counters.models_used[model] += 1
            if is_byok:
                counters.byok_calls += 1

    def snapshot(self) -> dict[str, Any]:
        """Return a JSON-serializable view of the counters."""
        with self._lock:
            specialists = []
            for c in self._counters.values():
                avg_ms = (
                    int(c.total_elapsed_ms / c.calls) if c.calls else 0
                )
                specialists.append(
                    {
                        "name": c.name,
                        "calls": c.calls,
                        "successes": c.successes,
                        "failures": c.failures,
                        "input_tokens": c.input_tokens,
                        "output_tokens": c.output_tokens,
                        "total_tokens": c.input_tokens + c.output_tokens,
                        "total_elapsed_ms": c.total_elapsed_ms,
                        "avg_elapsed_ms": avg_ms,
                        "byok_calls": c.byok_calls,
                        "last_called_at": c.last_called_at,
                        "last_model": c.last_model,
                        "last_error": c.last_error,
                        "models_used": dict(c.models_used),
                    }
                )
            # Stable order so the UI doesn't jitter; sort by calls desc
            # then name asc.
            specialists.sort(key=lambda s: (-s["calls"], s["name"]))
            return {
                "process_started_at": self._started_at,
                "uptime_seconds": int(time.time() - self._started_at),
                "specialists": specialists,
            }

    def reset(self) -> None:
        """Wipe the counters. Intended for tests and admin nukes."""
        with self._lock:
            self._counters.clear()
            self._started_at = time.time()


_instance: SpecialistMetrics | None = None


def get_specialist_metrics() -> SpecialistMetrics:
    """Return the process-wide ``SpecialistMetrics`` singleton."""
    global _instance
    if _instance is None:
        _instance = SpecialistMetrics()
    return _instance
