"""Perigee MCP layer.

Every tool call in the platform flows through `mcp.server`, decorated
with `gateway.audit_and_limit`. Specialists use `mcp.client.PerigeeMCPClient`
to call tools -- no direct imports of services/* from agents/*.

External MCP clients (Claude Desktop, Cursor) can connect to the same
server over HTTP+SSE at /mcp.
"""

from app.mcp.client import PerigeeMCPClient

__all__ = ["PerigeeMCPClient"]
