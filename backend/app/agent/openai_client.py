"""OpenAI-compatible streaming client (httpx, `/chat/completions`).

Used when `LLM_BASE_URL` and `LLM_API_KEY` are set; otherwise the app falls back
to `FakeLLM` (see `app/agent/__init__.py: build_llm`).
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Sequence
from typing import Any

import httpx

from app.agent.base import AgentContext, ChatTurn, KbSnippet, LLMEvent, ToolCall

SYSTEM_PROMPT = (
    "Ты — AI-buddy, ИИ-наставник стажёров Авито. Отвечаешь по-русски, кратко и по делу, "
    "по базе знаний и с цитированием источников. Действия (заявки, отметки чек-листа) "
    "выполняешь только через инструменты и только после явного подтверждения пользователя. "
    "Не раскрываешь данные, недоступные роли пользователя."
)

ROLE_POLICY = (
    "\n\nПолитика роли: согласуй формулировки с ролью пользователя — руководитель и "
    "наставник являются согласующей стороной, не предлагай им обратиться к себе; "
    "HR BP ведёт финальный контроль, а стажёр согласует заявки с руководителем."
)

TOOL_POLICY = (
    "\n\nПравила:\n"
    "1. Каждый факт подкрепляй источником: «— по материалу «Название документа»».\n"
    "2. Доступные инструменты: {tools}. Вызывай их только когда пользователь просит "
    "выполнить действие, а не когда спрашивает, как это делается.\n"
    "3. Дату для absence_create уточняй только если её нет в сообщении. Принимаются и "
    "«сегодня»/«завтра»/«послезавтра», и ISO-дата YYYY-MM-DD: передавай дату так, как "
    "сказал пользователь, просить его переводить в другой формат не нужно. Причина не "
    "обязательна: если её нет в переписке — создай черновик без неё и предложи дописать.\n"
    "4. НИКОГДА не создавай заявку без явного подтверждения пользователя в переписке. "
    "Подтверждение («подтверждаю») обрабатывается отдельно: не выдумывай результат "
    "подтверждения и не подтверждай заявку сам.\n"
    "5. Если инструмент вернул ошибку — честно сообщи об этом, не придумывай успех.\n"
    "6. Не выполняй действий от имени другого пользователя: личность берётся из сессии.\n"
    "7. Идентификатор пользователя известен системе; НЕ запрашивай user_id и служебные "
    "параметры; спрашивай только дату и причину.\n"
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
        sources: Sequence[KbSnippet] = (),
    ) -> dict[str, Any]:
        role_label = context.role.value
        system = (
            f"{SYSTEM_PROMPT}\n\nПользователь: {context.full_name} (роль: {role_label}). "
            f"Чек-лист: {context.done_count}/{len(context.checklist)} выполнено."
            f"{ROLE_POLICY}"
        )
        tool_names = [schema["function"]["name"] for schema in tools or ()]
        system += TOOL_POLICY.format(tools=", ".join(tool_names) or "нет")
        if sources:
            knowledge = "\n\n".join(
                f"[{snippet.title} — {snippet.source_url}]\n{snippet.content}".strip()
                for snippet in sources
            )
            system += (
                "\n\nФрагменты базы знаний (опирайся на них и ссылайся на источник):\n" + knowledge
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

    async def stream_turn(
        self,
        messages: Sequence[ChatTurn],
        context: AgentContext,
        tools: Sequence[dict[str, Any]] | None = None,
        sources: Sequence[KbSnippet] = (),
    ) -> AsyncIterator[LLMEvent]:
        """Text tokens as they arrive, then one event per completed tool call.

        Providers split a tool call across chunks: the id and name come first, the
        JSON arguments arrive in fragments. Accumulating by `index` is what turns
        that into one callable request (and what used to be silently dropped).
        """
        payload = self.build_payload(messages, context, tools, sources)
        client = self._client or httpx.AsyncClient(timeout=self._timeout)
        owns_client = self._client is None
        pending: dict[int, dict[str, str]] = {}
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
                    choices = chunk.get("choices") or []
                    if not choices:
                        # Providers emit usage/heartbeat chunks with an empty choices list.
                        continue
                    delta = choices[0].get("delta") or {}
                    content = delta.get("content")
                    if content:
                        yield LLMEvent(kind="token", text=content)
                    for raw_call in delta.get("tool_calls") or ():
                        slot = pending.setdefault(
                            int(raw_call.get("index", 0)), {"id": "", "name": "", "arguments": ""}
                        )
                        if raw_call.get("id"):
                            slot["id"] = raw_call["id"]
                        function = raw_call.get("function") or {}
                        slot["name"] += function.get("name") or ""
                        slot["arguments"] += function.get("arguments") or ""
        finally:
            if owns_client:
                await client.aclose()

        for index in sorted(pending):
            slot = pending[index]
            if not slot["name"]:
                continue
            yield LLMEvent(
                kind="tool_call",
                tool_call=ToolCall(
                    name=slot["name"], arguments=slot["arguments"] or "{}", call_id=slot["id"]
                ),
            )

    async def stream(
        self,
        messages: Sequence[ChatTurn],
        context: AgentContext,
        tools: Sequence[dict[str, Any]] | None = None,
        sources: Sequence[KbSnippet] = (),
    ) -> AsyncIterator[str]:
        """Plain text stream (the `LLMClient` contract); tool calls are dropped here."""
        async for event in self.stream_turn(messages, context, tools, sources):
            if event.kind == "token":
                yield event.text
