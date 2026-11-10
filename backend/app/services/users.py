"""User lookup and authentication."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import NotFoundError, UnauthorizedError
from app.models import Role, User
from app.security import verify_password


async def get_by_email(session: AsyncSession, email: str) -> User | None:
    result = await session.execute(select(User).where(User.email == email.strip().lower()))
    return result.scalar_one_or_none()


async def get_user(session: AsyncSession, user_id: int) -> User:
    user = await session.get(User, user_id)
    if user is None:
        raise NotFoundError("Пользователь не найден")
    return user


async def authenticate(session: AsyncSession, email: str, password: str) -> User:
    user = await get_by_email(session, email)
    if user is None or not verify_password(password, user.password_hash):
        raise UnauthorizedError("Неверный email или пароль")
    return user


async def first_intern(session: AsyncSession, actor: User) -> User:
    """The intern whose checklist/absences a privileged user is looking at.

    Seed data has one intern per team, so "the intern of my team" is enough for
    the scaffold; the dashboard can pass an explicit user_id later.
    """
    if actor.role is Role.intern:
        return actor
    stmt = select(User).where(User.role == Role.intern)
    if actor.role is not Role.hr_bp and actor.team:
        stmt = stmt.where(User.team == actor.team)
    stmt = stmt.order_by(User.id)
    intern = (await session.execute(stmt)).scalars().first()
    if intern is None:
        raise NotFoundError("В команде нет стажёров")
    return intern
