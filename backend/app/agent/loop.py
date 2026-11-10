"""Agent loop: history + role context → LLM stream → events for SSE."""

from __future__ import annotations

from collections.abc import AsyncIterator, Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.actions import execute_action
from app.agent.base import (
    AgentContext,
    AgentEvent,
    ChatTurn,
    ChecklistSnapshot,
    ContactSnapshot,
    KbSnippet,
    LLMClient,
    split_chunks,
)
from app.agent.tools import TOOL_SCHEMAS
from app.models import User
from app.services import checklist as checklist_service
from app.services import contacts as contacts_service
from app.services import kb as kb_service
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


async def retrieve_sources(session: AsyncSession | None, message: str) -> list[KbSnippet]:
    """Keyword retrieval over `kb_documents`; empty when there is no session/DB."""
    if session is None:
        return []
    documents = await kb_service.search(session, message)
    return [
        KbSnippet(title=document.title, source_url=document.source_url, content=document.content)
        for document in documents
    ]


class Agent:
    def __init__(self, llm: LLMClient) -> None:
        self.llm = llm

    async def stream(
        self,
        message: str,
        history: Sequence[ChatTurn],
        context: AgentContext,
        *,
        session: AsyncSession | None = None,
        user: User | None = None,
    ) -> AsyncIterator[AgentEvent]:
        turns = [*history[-MAX_HISTORY_TURNS:], ChatTurn(role="user", content=message)]
        # Both clients get the tool schemas (they mirror `mcp_server/tools.py` one-to-one).
        # Scaffold limitation: only `FakeLLM.plan()` actions are executed below. The
        # OpenAI-compatible client's streamed `tool_calls` are passed to the provider but
        # not yet fed back as role="tool" turns — wiring that to the MCP client is the
        # remaining step, and it would call the same `execute_action` seam.
        tools = TOOL_SCHEMAS
        sources = await retrieve_sources(session, message)

        planner = getattr(self.llm, "plan", None)
        action = planner(message, context) if planner is not None and session and user else None
        if action is not None and session is not None and user is not None:
            result = await execute_action(session, user, action)
            yield AgentEvent(kind="tool_call", data=result.data)
            for chunk in split_chunks(result.text):
                yield AgentEvent(kind="token", text=chunk)
            yield AgentEvent(kind="done", data={"sources": [s.as_source() for s in sources]})
            return

        async for token in self.llm.stream(turns, context, tools, sources):
            yield AgentEvent(kind="token", text=token)
        yield AgentEvent(kind="done", data={"sources": [s.as_source() for s in sources]})
