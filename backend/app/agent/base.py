"""Agent contract: context snapshot, LLM client protocol, stream events."""

from __future__ import annotations

from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

from app.models import Role


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


class LLMClient(Protocol):
    """A streaming chat-completions client."""

    name: str

    def stream(
        self,
        messages: Sequence[ChatTurn],
        context: AgentContext,
        tools: Sequence[dict[str, Any]] | None = None,
    ) -> AsyncIterator[str]: ...
