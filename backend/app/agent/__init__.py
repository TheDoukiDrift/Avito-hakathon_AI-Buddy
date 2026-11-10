"""LLM abstraction: OpenAI-compatible client when configured, deterministic FakeLLM otherwise."""

from app.agent.base import (
    AgentContext,
    AgentEvent,
    ChatTurn,
    ChecklistSnapshot,
    ContactSnapshot,
    LLMClient,
)
from app.agent.fake import FakeLLM
from app.agent.loop import Agent, build_context
from app.agent.openai_client import OpenAICompatibleClient
from app.agent.tools import TOOL_SCHEMAS
from app.config import Settings


def build_llm(settings: Settings) -> LLMClient:
    if settings.llm_enabled:
        return OpenAICompatibleClient(
            base_url=settings.llm_base_url,
            api_key=settings.llm_api_key,
            model=settings.llm_model,
            timeout=settings.llm_timeout_seconds,
        )
    return FakeLLM()


__all__ = [
    "Agent",
    "AgentContext",
    "AgentEvent",
    "ChatTurn",
    "ChecklistSnapshot",
    "ContactSnapshot",
    "FakeLLM",
    "LLMClient",
    "OpenAICompatibleClient",
    "TOOL_SCHEMAS",
    "build_context",
    "build_llm",
]
