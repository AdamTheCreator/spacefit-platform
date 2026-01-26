"""
Task request schema.

Submitted by sub-agents to the Connector Platform when they need data
from a third-party source.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class TaskRequest(BaseModel):
    """
    Represents a single unit of work for a connector to execute.
    """

    task_id: str = Field(default_factory=lambda: uuid4().hex)
    trace_id: str = Field(
        default_factory=lambda: uuid4().hex,
        description="Correlation ID for distributed tracing",
    )

    # What to fetch
    connector_id: str | None = Field(
        default=None,
        description="Explicit connector. If None, the router selects one.",
    )
    capability: str = Field(
        ..., description="Required capability tag, e.g. 'visitor_traffic'"
    )

    # Execution preference
    preferred_mode: str | None = Field(
        default=None,
        description="Preferred execution mode override (api, hybrid, browser)",
    )

    # Caller context
    tenant_id: str = Field(..., description="User / tenant ID for isolation")
    params: dict[str, Any] = Field(
        default_factory=dict,
        description="Connector-specific parameters (address, radius, date_range, …)",
    )

    # Credentials reference
    credential_id: str | None = Field(
        default=None,
        description="ID of the SiteCredential to use for auth",
    )

    # Scheduling
    timeout_seconds: int | None = Field(
        default=None,
        description="Per-request timeout override. Falls back to manifest limit.",
    )

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
