"""Agent loop: history + role context → LLM stream → events for SSE."""

from __future__ import annotations

import re
from collections.abc import AsyncIterator, Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.actions import (
    ACTION_ABSENCE_CONFIRM,
    AgentAction,
    execute_action,
    execute_tool_call,
    is_confirmation,
)
from app.agent.base import (
    AgentContext,
    AgentEvent,
    ChatTurn,
    ChecklistSnapshot,
    ContactSnapshot,
    KbSnippet,
    LLMClient,
    ToolCall,
    split_chunks,
)
from app.agent.tools import TOOL_SCHEMAS
from app.models import User
from app.services import checklist as checklist_service
from app.services import contacts as contacts_service
from app.services import kb as kb_service
from app.services import users as users_service

MAX_HISTORY_TURNS = 20

# A short or anaphoric follow-up ("а какие сроки?") carries no topic of its own, so
# retrieval adds the previous question — that is what makes follow-ups work offline.
_ANAPHORA_RE = re.compile(r"^\s*(а|и|но|ещё|еще|тогда|там|это)\b", re.IGNORECASE)


def _needs_history(message: str) -> bool:
    words = [word for word in message.split() if len(word) > 2]
    return len(words) <= 3 or bool(_ANAPHORA_RE.match(message))


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
    """Top-ranked chunks with their scores; empty when there is no session/DB."""
    if session is None:
        return []
    sources = await kb_service.search(session, message)
    return [
        KbSnippet(
            title=source.title,
            source_url=source.source_url,
            content=source.content,
            score=source.score,
        )
        for source in sources
    ]


def unique_sources(snippets: Sequence[KbSnippet]) -> list[KbSnippet]:
    """One entry per document for the SSE `sources` list (chunks stay for the model)."""
    seen: set[str] = set()
    unique: list[KbSnippet] = []
    for snippet in snippets:
        if snippet.title in seen:
            continue
        seen.add(snippet.title)
        unique.append(snippet)
    return unique


def relevant_sources(snippets: Sequence[KbSnippet], ratio: float = 0.7) -> list[KbSnippet]:
    """Keep the top document's chunks plus other documents close to the best score.

    A chunk from another document far below the best hit is usually an accidental
    word overlap; citing it would make the answer look random.
    """
    if not snippets:
        return []
    best = snippets[0].score
    top_title = snippets[0].title
    return [
        snippet
        for snippet in snippets
        if snippet.title == top_title or snippet.score >= best * ratio
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
        # Confirmation is policy, not model output: «подтверждаю» always targets the
        # caller's own latest draft. Handling it before the LLM keeps both paths
        # identical and saves a token round-trip on the OpenAI path.
        if session is not None and user is not None and is_confirmation(message):
            result = await execute_action(session, user, AgentAction(ACTION_ABSENCE_CONFIRM, {}))
            yield AgentEvent(kind="tool_call", data={**result.data, "tool": "absence_confirm"})
            for chunk in split_chunks(result.text):
                yield AgentEvent(kind="token", text=chunk)
            yield AgentEvent(kind="done", data={"sources": []})
            return

        turns = [*history[-MAX_HISTORY_TURNS:], ChatTurn(role="user", content=message)]
        # Both clients get the tool schemas (they mirror `mcp_server/tools.py` one-to-one).
        tools = TOOL_SCHEMAS
        query = message
        if history and _needs_history(message):
            previous = next((turn.content for turn in reversed(history) if turn.role == "user"), "")
            if previous:
                query = f"{previous} {message}"
        sources = relevant_sources(await retrieve_sources(session, query))

        planner = getattr(self.llm, "plan", None)
        action = planner(message, context) if planner is not None and session and user else None
        if action is not None and session is not None and user is not None:
            result = await execute_action(session, user, action)
            yield AgentEvent(kind="tool_call", data=result.data)
            for chunk in split_chunks(result.text):
                yield AgentEvent(kind="token", text=chunk)
            yield AgentEvent(
                kind="done", data={"sources": [s.as_source() for s in unique_sources(sources)]}
            )
            return

        # Tool loop for the OpenAI-compatible path: stream text, collect the model's
        # tool calls, then run them through the services layer and answer with the
        # deterministic result. An answer is never blank just because the model
        # emitted a tool call instead of prose.
        tool_stream = getattr(self.llm, "stream_turn", None)
        if tool_stream is not None and session is not None and user is not None:
            calls: list[ToolCall] = []
            async for event in tool_stream(turns, context, tools, sources):
                if event.kind == "token" and event.text:
                    yield AgentEvent(kind="token", text=event.text)
                elif event.kind == "tool_call" and event.tool_call is not None:
                    calls.append(event.tool_call)

            if calls:
                results = []
                for call in calls:
                    result = await execute_tool_call(session, user, call)
                    results.append((call, result))
                    yield AgentEvent(
                        kind="tool_call",
                        data={
                            "tool": call.name,
                            "call_id": call.call_id,
                            "arguments": call.arguments,
                            **result.data,
                        },
                    )
                summary = "\n\n".join(result.text for _, result in results)
                for chunk in split_chunks(summary):
                    yield AgentEvent(kind="token", text=chunk)
            yield AgentEvent(
                kind="done", data={"sources": [s.as_source() for s in unique_sources(sources)]}
            )
            return

        async for token in self.llm.stream(turns, context, tools, sources):
            yield AgentEvent(kind="token", text=token)
        yield AgentEvent(
            kind="done", data={"sources": [s.as_source() for s in unique_sources(sources)]}
        )
