"""Agent contract: context snapshot, LLM client protocol, stream events."""

from __future__ import annotations

import re
from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

from app.models import Role


def split_chunks(text: str) -> list[str]:
    """Split text into word-sized chunks so SSE looks like a real token stream."""
    return [chunk for chunk in re.split(r"(\s+)", text) if chunk]


@dataclass
class ChecklistSnapshot:
    title: str
    week: int
    done: bool


@dataclass
class ContactSnapshot:
    name: str
    role: str
    email: str


@dataclass
class AgentContext:
    """Everything the model may know about the caller — assembled from services."""

    full_name: str
    role: Role
    checklist: list[ChecklistSnapshot] = field(default_factory=list)
    contacts: list[ContactSnapshot] = field(default_factory=list)

    @property
    def done_count(self) -> int:
        return sum(1 for item in self.checklist if item.done)

    @property
    def next_pending(self) -> ChecklistSnapshot | None:
        return next((item for item in self.checklist if not item.done), None)


@dataclass
class ChatTurn:
    role: Literal["user", "assistant"]
    content: str


@dataclass
class AgentEvent:
    kind: Literal["token", "tool_call", "done"]
    text: str = ""
    data: dict[str, Any] | None = None


@dataclass
class KbSnippet:
    """A retrieved knowledge-base chunk as the model/UI may see it."""

    title: str
    source_url: str
    content: str = ""
    score: float = 0.0

    def as_source(self) -> dict[str, str]:
        return {"title": self.title, "source_url": self.source_url}


class LLMClient(Protocol):
    """A streaming chat-completions client."""

    name: str

    def stream(
        self,
        messages: Sequence[ChatTurn],
        context: AgentContext,
        tools: Sequence[dict[str, Any]] | None = None,
        sources: Sequence[KbSnippet] = (),
    ) -> AsyncIterator[str]: ...
