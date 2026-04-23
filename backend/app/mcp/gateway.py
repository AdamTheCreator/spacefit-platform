"""Gateway middleware for MCP tools.

Every tool goes through `audit_and_limit(tool_name)`:
  1. Rate limit check (per-user, per-tool)
  2. Authorization check (subscription tier -> allowed tools)
  3. Execute tool
  4. Audit log row (success or failure)
  5. Analytics metric emission

User attribution is passed via contextvars (see mcp.context) — the
SpacegooseMCPClient sets them before calling, so tool function signatures
stay clean (MCP SDK rejects parameter names starting with '_').
"""

from __future__ import annotations

import asyncio
import functools
import json
import logging
import time
from typing import Any, Awaitable, Callable

from app.core.database import async_session_factory
from app.db.models.tool_call import ToolCallLog
from app.mcp.context import current_session_id, current_user_id
from app.services.analytics import get_analytics

logger = logging.getLogger(__name__)

# Per-user, per-tool rate limits (calls per minute).
RATE_LIMITS_PER_MIN: dict[str, int] = {
    "business_search": 30,
    "demographics_analysis": 30,
    "tenant_roster": 30,
    "void_analysis": 20,
    "costar_import": 60,
    "placer_import": 60,
    "siteusa_import": 60,
    "draft_outreach": 10,
}

# In-process rate limit counter.  Single-process deployment.
_recent_calls: dict[tuple[str, str], list[float]] = {}
_rate_lock = asyncio.Lock()


class ToolRateLimitError(Exception):
    """Raised when a user hits the per-tool rate limit."""


async def _enforce_rate_limit(user_id: str, tool_name: str) -> None:
    limit = RATE_LIMITS_PER_MIN.get(tool_name, 60)
    now = time.time()
    key = (user_id, tool_name)
    async with _rate_lock:
        history = _recent_calls.setdefault(key, [])
        history[:] = [t for t in history if now - t < 60]
        if len(history) >= limit:
            raise ToolRateLimitError(
                f"Rate limit: {tool_name} is capped at {limit}/min per user."
            )
        history.append(now)


async def _check_authorization(user_id: str, tool_name: str) -> None:
    """Subscription-tier gating.  For v1, all tools are available on all tiers."""
    pass


async def _log_tool_call(
    *,
    user_id: str,
    session_id: str | None,
    tool_name: str,
    arguments: dict,
    status: str,
    elapsed_ms: int,
    error_message: str | None,
) -> None:
    try:
        async with async_session_factory() as db:
            log = ToolCallLog(
                user_id=user_id,
                session_id=session_id,
                tool_name=tool_name,
                arguments_json=json.dumps(arguments, default=str)[:10_000],
                status=status,
                elapsed_ms=elapsed_ms,
                error_message=error_message,
            )
            db.add(log)
            await db.commit()
    except Exception as e:
        # Audit log is best-effort -- don't fail the tool call if logging fails.
        logger.warning("Failed to write tool_call_log: %s", e)


def audit_and_limit(tool_name: str) -> Callable:
    """Decorator: wraps an MCP tool with rate limiting, authz, audit, and metrics.

    Reads user attribution from contextvars (set by SpacegooseMCPClient).
    """

    def decorator(fn: Callable[..., Awaitable[Any]]) -> Callable[..., Awaitable[Any]]:
        @functools.wraps(fn)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            user_id = current_user_id.get()
            session_id = current_session_id.get()
            if not user_id:
                logger.warning(
                    "Tool %s called without user context -- audit will use 'anonymous'",
                    tool_name,
                )
                user_id = "anonymous"

            # Rate limit + authz
            try:
                await _enforce_rate_limit(user_id, tool_name)
                await _check_authorization(user_id, tool_name)
            except ToolRateLimitError as e:
                await _log_tool_call(
                    user_id=user_id,
                    session_id=session_id,
                    tool_name=tool_name,
                    arguments=kwargs,
                    status="rate_limited",
                    elapsed_ms=0,
                    error_message=str(e),
                )
                return f"Rate limited: {e}"

            # Execute
            t0 = time.monotonic()
            status = "ok"
            error: str | None = None
            try:
                result = await fn(*args, **kwargs)
                return result
            except Exception as e:
                status = "error"
                error = f"{type(e).__name__}: {e}"
                raise
            finally:
                elapsed_ms = int((time.monotonic() - t0) * 1000)
                await _log_tool_call(
                    user_id=user_id,
                    session_id=session_id,
                    tool_name=tool_name,
                    arguments=kwargs,
                    status=status,
                    elapsed_ms=elapsed_ms,
                    error_message=error,
                )
                try:
                    get_analytics().record_tool_result(
                        tool_name=tool_name,
                        success=(status == "ok"),
                        user_id=user_id,
                        conversation_id=session_id,
                        duration_ms=elapsed_ms,
                    )
                except Exception:
                    pass  # analytics best-effort

        return wrapper

    return decorator
