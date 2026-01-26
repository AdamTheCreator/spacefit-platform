"""
Connector response envelope.

Every connector execution returns this consistent structure regardless
of execution mode (API, browser, hybrid).
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ResponseStatus(str, Enum):
    SUCCESS = "success"
    FAILURE = "failure"
    PARTIAL = "partial"
    USER_ACTION_REQUIRED = "user_action_required"


class Provenance(BaseModel):
    """Audit trail for the data returned."""

    source_connector: str = ""
    execution_mode: str = ""
    pages_visited: list[str] = Field(default_factory=list)
    extraction_summary: str = ""
    started_at: datetime | None = None
    finished_at: datetime | None = None
    workflow_steps_executed: int = 0


class Metrics(BaseModel):
    """Performance telemetry for the execution."""

    latency_ms: int = 0
    pages_visited: int = 0
    bytes_extracted: int = 0
    api_calls_made: int = 0
    retries: int = 0


class ErrorDetail(BaseModel):
    """Standardized error structure."""

    code: str = ""
    message: str = ""
    severity: str = "error"  # error, warning, info
    remediation: str = ""
    details: dict[str, Any] = Field(default_factory=dict)


class ConnectorResponse(BaseModel):
    """
    The universal response envelope returned by every connector execution.
    """

    task_id: str
    trace_id: str
    status: ResponseStatus
    data: dict[str, Any] | list[Any] | None = None
    provenance: Provenance = Field(default_factory=Provenance)
    metrics: Metrics = Field(default_factory=Metrics)
    errors: list[ErrorDetail] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    # Debug artifacts (only populated on failure when debug is enabled)
    debug_artifacts: dict[str, str] = Field(
        default_factory=dict,
        description="Paths to screenshots, console logs, network logs on failure",
    )
