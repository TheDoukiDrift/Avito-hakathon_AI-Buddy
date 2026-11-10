"""Audit trail — every mutating scenario writes here (case requirement)."""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditEvent


async def log(
    session: AsyncSession, user_id: int | None, action: str, payload: dict[str, Any] | None = None
) -> AuditEvent:
    event = AuditEvent(user_id=user_id, action=action, payload=payload or {})
    session.add(event)
    await session.flush()
    return event


async def list_events(session: AsyncSession, limit: int = 50) -> list[AuditEvent]:
    from sqlalchemy import select

    result = await session.execute(select(AuditEvent).order_by(AuditEvent.id.desc()).limit(limit))
    return list(result.scalars())
