"""FastAPI dependencies: bearer auth and role guards."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.errors import ForbiddenError, UnauthorizedError
from app.models import Role, User
from app.security import decode_token
from app.services import users as users_service

bearer_scheme = HTTPBearer(auto_error=False)

_ROLE_LABELS = {
    Role.intern: "стажёр",
    Role.mentor: "наставник",
    Role.manager: "руководитель",
    Role.hr_bp: "HR BP",
}


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    session: AsyncSession = Depends(get_session),
) -> User:
    if credentials is None or not credentials.credentials:
        raise UnauthorizedError("Нужен заголовок Authorization: Bearer <token>")
    user_id = decode_token(credentials.credentials)
    if user_id is None:
        raise UnauthorizedError("Токен недействителен или истёк")
    return await users_service.get_user(session, user_id)


def require_roles(*roles: Role) -> Callable[[User], Awaitable[User]]:
    """Guard for endpoints that are role-only (no ownership attribute)."""

    async def _guard(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            allowed = ", ".join(_ROLE_LABELS[role] for role in roles)
            raise ForbiddenError(f"Доступно только роли: {allowed}")
        return user

    return _guard


def client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"
