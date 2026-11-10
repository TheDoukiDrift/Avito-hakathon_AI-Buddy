"""FastMCP server exposing the services layer as MCP tools.

Run as its own process: `python -m mcp_server` (streamable-http on :8001, so
docker-compose can expose it next to the API).
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from app.config import get_settings
from mcp_server import tools

SERVER_NAME = "ai-buddy-tools"
SERVER_INSTRUCTIONS = (
    "Инструменты адаптации стажёра: отсутствия, чек-лист, контакты. "
    "Каждый инструмент проверяет роль и права пользователя на стороне сервисов."
)


def build_server() -> FastMCP:
    settings = get_settings()
    server = FastMCP(
        SERVER_NAME,
        instructions=SERVER_INSTRUCTIONS,
        host=settings.mcp_host,
        port=settings.mcp_port,
    )
    for tool in tools.TOOLS:
        server.tool()(tool)
    return server


server = build_server()


def main() -> None:
    server.run(transport="streamable-http")


if __name__ == "__main__":  # pragma: no cover
    main()
