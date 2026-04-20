"""Context variables for MCP tool attribution.

The PerigeeMCPClient sets these before calling a tool; the gateway
reads them for audit logging and rate limiting. This avoids polluting
tool function signatures with internal parameters (MCP SDK rejects
parameter names starting with '_').
"""

from __future__ import annotations

from contextvars import ContextVar

current_user_id: ContextVar[str] = ContextVar("current_user_id", default="")
current_session_id: ContextVar[str | None] = ContextVar("current_session_id", default=None)
