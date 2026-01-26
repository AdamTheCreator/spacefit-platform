"""
Observability for the Connector Platform.

Provides:
- Structured logging with trace_id
- Per-connector metrics collection
- Retry-with-backoff utility
- Debug artifact tracking
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, TypeVar

from app.connectors.schemas.errors import ConnectorError, ErrorSeverity

logger = logging.getLogger("connectors.telemetry")

T = TypeVar("T")


@dataclass
class TraceContext:
    trace_id: str = ""
    task_id: str = ""
    connector_id: str = ""
    started_at: float = 0.0
    events: list[dict[str, Any]] = field(default_factory=list)


class ConnectorTelemetry:
    """
    Collects telemetry for a single connector execution.
    """

    def __init__(self, connector_id: str) -> None:
        self.connector_id = connector_id
        self._trace: TraceContext | None = None
        self._metrics: dict[str, Any] = defaultdict(int)

    # ------------------------------------------------------------------
    # Tracing
    # ------------------------------------------------------------------

    def start_trace(self, trace_id: str, task_id: str) -> None:
        self._trace = TraceContext(
            trace_id=trace_id,
            task_id=task_id,
            connector_id=self.connector_id,
            started_at=time.monotonic(),
        )
        self._log("trace_start", task_id=task_id)

    def finish_trace(self, *, success: bool, latency_ms: int) -> None:
        self._log(
            "trace_end",
            success=success,
            latency_ms=latency_ms,
        )
        self._trace = None

    # ------------------------------------------------------------------
    # Event recording
    # ------------------------------------------------------------------

    def record_api_call(
        self,
        url: str,
        method: str,
        status_code: int,
        latency_ms: int,
    ) -> None:
        self._metrics["api_calls"] += 1
        self._log(
            "api_call",
            url=url,
            method=method,
            status_code=status_code,
            latency_ms=latency_ms,
        )

    def record_page_visit(self, url: str) -> None:
        self._metrics["pages_visited"] += 1
        self._log("page_visit", url=url)

    def record_error(self, error: ConnectorError) -> None:
        self._metrics["errors"] += 1
        self._log(
            "error",
            code=error.code.value,
            message=error.message,
            severity=error.severity.value,
            retryable=error.retryable,
        )

    def record_retry(self, attempt: int, reason: str) -> None:
        self._metrics["retries"] += 1
        self._log("retry", attempt=attempt, reason=reason)

    # ------------------------------------------------------------------
    # Structured logging
    # ------------------------------------------------------------------

    def _log(self, event: str, **kwargs: Any) -> None:
        extra = {
            "connector_id": self.connector_id,
            "event": event,
            **kwargs,
        }
        if self._trace:
            extra["trace_id"] = self._trace.trace_id
            extra["task_id"] = self._trace.task_id

        logger.info(
            "[%s] %s %s",
            self.connector_id,
            event,
            " ".join(f"{k}={v}" for k, v in kwargs.items()),
            extra=extra,
        )

        if self._trace:
            self._trace.events.append({"event": event, "ts": time.time(), **kwargs})

    # ------------------------------------------------------------------
    # Metrics summary
    # ------------------------------------------------------------------

    def get_metrics_summary(self) -> dict[str, Any]:
        return dict(self._metrics)


# ---------------------------------------------------------------------------
# Retry utility
# ---------------------------------------------------------------------------

async def retry_with_backoff(
    fn: Callable[..., Awaitable[T]],
    *args: Any,
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    telemetry: ConnectorTelemetry | None = None,
    **kwargs: Any,
) -> T:
    """
    Call *fn* up to *max_retries* times, retrying only on transient
    ConnectorErrors with exponential backoff.
    """
    last_exc: Exception | None = None

    for attempt in range(1, max_retries + 1):
        try:
            return await fn(*args, **kwargs)
        except ConnectorError as exc:
            last_exc = exc
            if not exc.retryable or attempt == max_retries:
                raise
            delay = min(base_delay * (2 ** (attempt - 1)), max_delay)
            if telemetry:
                telemetry.record_retry(attempt, exc.message)
            logger.warning(
                "Retrying (%d/%d) after %.1fs: %s",
                attempt, max_retries, delay, exc.message,
            )
            await asyncio.sleep(delay)

    # Should not reach here, but just in case
    raise last_exc  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Aggregate metrics store (in-memory, per-process)
# ---------------------------------------------------------------------------

class MetricsStore:
    """
    Process-level aggregation of connector metrics.

    Tracks:
    - success_rate per connector
    - auth_failure_rate per connector
    - median_latency per connector
    - layout_change_rate per connector
    """

    def __init__(self) -> None:
        self._executions: dict[str, list[dict]] = defaultdict(list)

    def record_execution(
        self,
        connector_id: str,
        success: bool,
        latency_ms: int,
        auth_failure: bool = False,
        layout_changed: bool = False,
    ) -> None:
        self._executions[connector_id].append({
            "success": success,
            "latency_ms": latency_ms,
            "auth_failure": auth_failure,
            "layout_changed": layout_changed,
            "ts": time.time(),
        })

    def get_stats(self, connector_id: str) -> dict[str, Any]:
        records = self._executions.get(connector_id, [])
        if not records:
            return {"total": 0}

        total = len(records)
        successes = sum(1 for r in records if r["success"])
        auth_failures = sum(1 for r in records if r["auth_failure"])
        layout_changes = sum(1 for r in records if r["layout_changed"])
        latencies = sorted(r["latency_ms"] for r in records)
        median_latency = latencies[len(latencies) // 2] if latencies else 0

        return {
            "total": total,
            "success_rate": successes / total if total else 0,
            "auth_failure_rate": auth_failures / total if total else 0,
            "median_latency_ms": median_latency,
            "layout_change_rate": layout_changes / total if total else 0,
        }

    def get_all_stats(self) -> dict[str, dict[str, Any]]:
        return {cid: self.get_stats(cid) for cid in self._executions}


# Singleton metrics store
metrics_store = MetricsStore()
