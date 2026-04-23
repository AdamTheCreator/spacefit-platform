"""In-process MCP client used by specialist agents and the orchestrator.

Specialists don't call services/* directly -- they go through this client,
which routes through the gateway (audit log, rate limit, attribution).

User attribution is set via contextvars before calling the tool function,
so tool signatures stay clean (MCP SDK rejects '_'-prefixed params).
"""

from __future__ import annotations

import logging
from typing import Any

from app.mcp.context import current_session_id, current_user_id

logger = logging.getLogger(__name__)

# Lazy import to avoid circular references at module load time.
_tool_registry: dict[str, Any] | None = None


def _get_tool_registry() -> dict[str, Any]:
    """Build a name -> callable mapping from registered MCP tools.

    FastMCP stores tools internally; we resolve the underlying wrapped
    function (with gateway decorators already applied) so we can call
    it directly with kwargs -- no MCP protocol overhead.
    """
    global _tool_registry
    if _tool_registry is not None:
        return _tool_registry

    from app.mcp.server import mcp  # noqa: E402

    # FastMCP stores tools in different attributes depending on version.
    # v1.27+: mcp._tool_manager._tools (dict[str, Tool])
    raw: dict | None = None
    for attr in ("_tool_manager", "_tools", "tools"):
        candidate = getattr(mcp, attr, None)
        if candidate is not None:
            for sub in ("_tools", "tools"):
                sub_val = getattr(candidate, sub, None)
                if isinstance(sub_val, dict) and sub_val:
                    raw = sub_val
                    break
            if raw:
                break
            if isinstance(candidate, dict) and candidate:
                raw = candidate
                break

    if not raw:
        raise RuntimeError(
            "Cannot locate FastMCP tool registry -- check mcp SDK version."
        )

    registry: dict[str, Any] = {}
    for name, tool_obj in raw.items():
        fn = getattr(tool_obj, "fn", None)
        if fn is None:
            logger.warning("MCP tool %r has no .fn attribute, skipping", name)
            continue
        registry[name] = fn

    _tool_registry = registry
    logger.info("MCP tool registry loaded: %s", list(registry.keys()))
    return registry


class SpacegooseMCPClient:
    """In-process MCP client. Each chat turn gets its own instance with
    the user + session attribution baked in."""

    def __init__(self, user_id: str, session_id: str | None = None) -> None:
        self.user_id = user_id
        self.session_id = session_id

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> str:
        """Call a Space Goose tool by name.

        Sets contextvars for user attribution, then calls the tool
        function directly. Gateway middleware (rate limit, audit log)
        reads the contextvars automatically.
        """
        registry = _get_tool_registry()
        fn = registry.get(name)
        if fn is None:
            return f"Unknown tool: {name}"

        # Set attribution context for the gateway decorator
        user_token = current_user_id.set(self.user_id)
        session_token = current_session_id.set(self.session_id)
        try:
            return await fn(**arguments)
        finally:
            current_user_id.reset(user_token)
            current_session_id.reset(session_token)

    async def list_tools(self) -> list[dict[str, str]]:
        """Return tool name + description pairs (useful for agent prompts)."""
        from app.mcp.server import mcp

        tools = await mcp.list_tools()
        return [{"name": t.name, "description": t.description or ""} for t in tools]
