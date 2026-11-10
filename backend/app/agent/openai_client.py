"""OpenAI-compatible streaming client (httpx, `/chat/completions`).

Used when `LLM_BASE_URL` and `LLM_API_KEY` are set; otherwise the app falls back
to `FakeLLM` (see `app/agent/__init__.py: build_llm`).
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Sequence
from typing import Any

import httpx

from app.agent.base import AgentContext, ChatTurn

SYSTEM_PROMPT = (
    "Ты — AI-buddy, помощник адаптации стажёров Авито. Отвечай кратко, по-русски, "
    "со ссылкой на источник. Действия (заявки, отметки чек-листа) выполняй только "
    "через инструменты и только после явного подтверждения пользователя. "
    "Не раскрывай данные, недоступные роли пользователя."
)


class OpenAICompatibleClient:
    name = "openai-compatible"

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str,
        timeout: float = 60.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self._timeout = timeout
        self._client = client

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def build_payload(
        self,
        messages: Sequence[ChatTurn],
        context: AgentContext,
        tools: Sequence[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        role_label = context.role.value
        system = (
            f"{SYSTEM_PROMPT}\n\nПользователь: {context.full_name} (роль: {role_label}). "
            f"Чек-лист: {context.done_count}/{len(context.checklist)} выполнено."
        )
        payload: dict[str, Any] = {
            "model": self.model,
            "stream": True,
            "messages": [{"role": "system", "content": system}]
            + [{"role": m.role, "content": m.content} for m in messages],
        }
        if tools:
            payload["tools"] = list(tools)
            payload["tool_choice"] = "auto"
        return payload

    async def stream(
        self,
        messages: Sequence[ChatTurn],
        context: AgentContext,
        tools: Sequence[dict[str, Any]] | None = None,
    ) -> AsyncIterator[str]:
        payload = self.build_payload(messages, context, tools)
        client = self._client or httpx.AsyncClient(timeout=self._timeout)
        owns_client = self._client is None
        try:
            async with client.stream(
                "POST", f"{self.base_url}/chat/completions", json=payload, headers=self._headers()
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    data = line[len("data:") :].strip()
                    if data == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data)
                    except json.JSONDecodeError:  # pragma: no cover - provider noise
                        continue
                    delta = chunk.get("choices", [{}])[0].get("delta", {})
                    content = delta.get("content")
                    if content:
                        yield content
        finally:
            if owns_client:
                await client.aclose()
