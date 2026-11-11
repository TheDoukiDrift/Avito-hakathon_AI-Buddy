"""SSE chat endpoint: tokens stream out while the answer is persisted."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent import Agent, ChatTurn, LLMClient, build_context, get_llm
from app.config import get_settings
from app.db import get_session, get_session_factory
from app.deps import get_current_user
from app.models import Conversation, MessageRole, User
from app.schemas import ChatRequest, MessageOut
from app.services import audit
from app.services import chat as chat_service

router = APIRouter(tags=["chat"])

SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}


def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


@router.post("/chat/stream")
async def chat_stream(
    payload: ChatRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    llm: LLMClient = Depends(get_llm),
):
    # Persist the question and build the context before the stream starts, so the
    # first byte is not blocked by a DB round-trip inside the generator.
    conversation = await chat_service.get_or_create_conversation(session, user)
    question = await chat_service.add_message(
        session, conversation, MessageRole.user, payload.message
    )
    await audit.log(session, user.id, "chat.message", {"chars": len(payload.message)})
    await session.commit()

    history = await chat_service.history(session, user)
    turns = [
        ChatTurn(role=message.role.value, content=message.content)
        for message in history
        if message.id != question.id
    ]
    context = await build_context(session, user)
    conversation_id = conversation.id
    user_id = user.id

    async def event_stream():
        agent = Agent(llm)
        parts: list[str] = []
        sources: list[dict] = []
        tool_calls: list[dict] = []
        # A dedicated session: the request-scoped one may already be closed by the time
        # the generator runs, and tool actions commit on their own.
        async with get_session_factory()() as agent_session:
            actor = await agent_session.get(User, user_id)
            if actor is None:  # pragma: no cover - token came from this user
                yield _sse({"error": "Пользователь не найден"})
                return
            try:
                async for event in agent.stream(
                    payload.message, turns, context, session=agent_session, user=actor
                ):
                    if event.kind == "token":
                        parts.append(event.text)
                        yield _sse({"token": event.text})
                    elif event.kind == "tool_call":
                        if event.data:
                            tool_calls.append(event.data)
                            yield _sse({"tool_call": event.data})
                    elif event.kind == "done" and event.data:
                        sources = event.data.get("sources") or []
            except Exception as exc:  # noqa: BLE001 - never break the stream silently
                yield _sse({"error": f"LLM недоступен: {exc.__class__.__name__}"})

        answer = "".join(parts).strip()
        message_id = None
        async with get_session_factory()() as persist_session:
            conversation_row = await persist_session.get(Conversation, conversation_id)
            if conversation_row is not None and answer:
                stored = await chat_service.add_message(
                    persist_session,
                    conversation_row,
                    MessageRole.assistant,
                    answer,
                    tool_calls=tool_calls or None,
                    sources=sources,
                )
                await audit.log(
                    persist_session,
                    user_id,
                    "chat.answer",
                    {
                        "chars": len(answer),
                        "llm": "api" if get_settings().llm_enabled else "fake",
                        "sources": [source.get("title") for source in sources],
                        "tools": [call.get("tool") for call in tool_calls],
                    },
                )
                await persist_session.commit()
                message_id = stored.id
        yield _sse({"done": True, "message_id": message_id, "sources": sources})

    return StreamingResponse(event_stream(), media_type="text/event-stream", headers=SSE_HEADERS)


@router.get("/chat/history", response_model=list[MessageOut])
async def chat_history(
    user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)
) -> list[MessageOut]:
    messages = await chat_service.history(session, user)
    return [MessageOut.model_validate(message) for message in messages]
