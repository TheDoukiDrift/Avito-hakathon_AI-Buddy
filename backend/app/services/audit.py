"""Audit trail — every mutating scenario writes here (case requirement)."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditEvent, Role, User
from app.services import rbac


async def log(
    session: AsyncSession, user_id: int | None, action: str, payload: dict[str, Any] | None = None
) -> AuditEvent:
    event = AuditEvent(user_id=user_id, action=action, payload=payload or {})
    session.add(event)
    await session.flush()
    return event


async def list_events(session: AsyncSession, limit: int = 50) -> list[AuditEvent]:
    result = await session.execute(select(AuditEvent).order_by(AuditEvent.id.desc()).limit(limit))
    return list(result.scalars())


async def list_for_actor(session: AsyncSession, actor: User, limit: int = 50) -> list[AuditEvent]:
    """Scoped audit feed: HR BP sees everything, mentors/managers their team, interns theirs.

    The matrix (`README`, `docs/DECISIONS.md`) promises audit visibility, so the scope is
    enforced here rather than by filtering in the router.
    """
    if not rbac.can_view_audit(actor):
        from app.errors import ForbiddenError

        raise ForbiddenError("Аудит событий недоступен вашей роли")

    stmt = select(AuditEvent)
    if actor.role is Role.hr_bp:
        pass
    elif actor.role in (Role.mentor, Role.manager):
        stmt = stmt.join(User, User.id == AuditEvent.user_id).where(User.team == actor.team)
    else:
        stmt = stmt.where(AuditEvent.user_id == actor.id)
    stmt = stmt.order_by(AuditEvent.id.desc()).limit(limit)
    return list((await session.execute(stmt)).scalars())
