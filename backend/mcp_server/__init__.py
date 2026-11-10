"""MCP server package (FastMCP) — separate process, shared services layer."""

from mcp_server.server import build_server

__all__ = ["build_server"]
