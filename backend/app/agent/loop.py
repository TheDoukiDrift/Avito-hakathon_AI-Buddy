"""Agent loop: history + role context → LLM stream → events for SSE."""

from __future__ import annotations

from collections.abc import AsyncIterator, Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.base import (
    AgentContext,
    AgentEvent,
    ChatTurn,
    ChecklistSnapshot,
    ContactSnapshot,
    LLMClient,
)
from app.agent.tools import TOOL_SCHEMAS
from app.models import User
from app.services import checklist as checklist_service
from app.services import contacts as contacts_service
from app.services import users as users_service

MAX_HISTORY_TURNS = 20


async def build_context(session: AsyncSession, user: User) -> AgentContext:
    """Snapshot what the model may see about this caller — never more than the role allows."""
    target = user
    if user.role.value != "intern":
        try:
            target = await users_service.first_intern(session, user)
        except Exception:  # noqa: BLE001 - no intern in the team is a normal state
            target = user

    entries = await checklist_service.get_checklist(session, target)
    contact_rows = await contacts_service.list_contacts(session, user)

    return AgentContext(
        full_name=user.full_name,
        role=user.role,
        checklist=[
            ChecklistSnapshot(
                title=entry.item.title,
                week=entry.item.week,
                done=entry.status.value == "done",
            )
            for entry in entries
        ],
        contacts=[
            ContactSnapshot(name=row.name, role=row.role, email=row.email) for row in contact_rows
        ],
    )


class Agent:
    def __init__(self, llm: LLMClient) -> None:
        self.llm = llm

    async def stream(
        self,
        message: str,
        history: Sequence[ChatTurn],
        context: AgentContext,
    ) -> AsyncIterator[AgentEvent]:
        turns = [*history[-MAX_HISTORY_TURNS:], ChatTurn(role="user", content=message)]
        tools = None if self.llm.name == "fake" else TOOL_SCHEMAS

        # TODO(mcp): when tools is not None, collect streamed tool_calls and execute
        # them through the MCP client (streamable-http at settings.mcp_url), then feed
        # the results back as role="tool" turns before the final answer. The tool
        # schemas already mirror `mcp_server/tools.py` one-to-one.
        async for token in self.llm.stream(turns, context, tools):
            yield AgentEvent(kind="token", text=token)
        yield AgentEvent(kind="done")
