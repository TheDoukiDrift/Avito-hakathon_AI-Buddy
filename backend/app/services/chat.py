"""Conversation persistence for the chat scenario."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Conversation, Message, MessageRole, User


async def get_or_create_conversation(session: AsyncSession, user: User) -> Conversation:
    result = await session.execute(
        select(Conversation)
        .where(Conversation.user_id == user.id)
        .order_by(Conversation.id.desc())
        .limit(1)
    )
    conversation = result.scalar_one_or_none()
    if conversation is None:
        conversation = Conversation(user_id=user.id)
        session.add(conversation)
        await session.flush()
    return conversation


async def add_message(
    session: AsyncSession,
    conversation: Conversation,
    role: MessageRole,
    content: str,
    tool_calls: list | dict | None = None,
    sources: list[dict] | None = None,
) -> Message:
    message = Message(
        conversation_id=conversation.id,
        role=role,
        content=content,
        tool_calls=tool_calls,
        sources=sources or None,
    )
    session.add(message)
    await session.flush()
    return message


async def history(session: AsyncSession, user: User, limit: int = 100) -> list[Message]:
    stmt = (
        select(Message)
        .join(Conversation, Conversation.id == Message.conversation_id)
        .where(Conversation.user_id == user.id)
        .order_by(Message.id)
        .limit(limit)
    )
    return list((await session.execute(stmt)).scalars())
