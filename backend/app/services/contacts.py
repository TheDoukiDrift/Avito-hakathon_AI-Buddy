"""Team contacts — the routing source for S4 «к кому обратиться»."""

from __future__ import annotations

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import ForbiddenError
from app.models import Contact, User
from app.services import rbac


async def list_contacts(
    session: AsyncSession, actor: User, query: str | None = None
) -> list[Contact]:
    if not rbac.can_view_contacts(actor):
        raise ForbiddenError("Контакты недоступны вашей роли")

    stmt = select(Contact)
    if actor.team:
        stmt = stmt.where(Contact.team == actor.team)
    if query:
        needle = f"%{query.strip().lower()}%"
        stmt = stmt.where(
            or_(
                Contact.name.ilike(needle),
                Contact.role.ilike(needle),
                Contact.email.ilike(needle),
            )
        )
    stmt = stmt.order_by(Contact.id)
    return list((await session.execute(stmt)).scalars())
