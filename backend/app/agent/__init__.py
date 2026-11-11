"""LLM abstraction: OpenAI-compatible client when configured, deterministic FakeLLM otherwise."""

from app.agent.base import (
    AgentContext,
    AgentEvent,
    ChatTurn,
    ChecklistSnapshot,
    ContactSnapshot,
    KbSnippet,
    LLMClient,
    LLMEvent,
    ToolCall,
)
from app.agent.dates import local_today, parse_date_phrase
from app.agent.fake import FakeLLM
from app.agent.loop import Agent, build_context
from app.agent.openai_client import OpenAICompatibleClient
from app.agent.tools import TOOL_SCHEMAS
from app.config import Settings, get_settings


def build_llm(settings: Settings) -> LLMClient:
    if settings.llm_enabled:
        return OpenAICompatibleClient(
            base_url=settings.llm_base_url,
            api_key=settings.llm_api_key,
            model=settings.llm_model,
            timeout=settings.llm_timeout_seconds,
        )
    return FakeLLM()


def get_llm() -> LLMClient:
    """FastAPI dependency; tests override it to inject a stub client (no network)."""
    return build_llm(get_settings())


__all__ = [
    "Agent",
    "AgentContext",
    "AgentEvent",
    "ChatTurn",
    "ChecklistSnapshot",
    "ContactSnapshot",
    "FakeLLM",
    "KbSnippet",
    "LLMClient",
    "LLMEvent",
    "OpenAICompatibleClient",
    "TOOL_SCHEMAS",
    "ToolCall",
    "build_context",
    "build_llm",
    "get_llm",
    "local_today",
    "parse_date_phrase",
]
