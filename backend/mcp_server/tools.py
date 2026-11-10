"""MCP tools — the only channel the agent has to the corporate-service imitations.

Each tool takes the caller identity explicitly (`user_id`, `role`) because MCP
carries no HTTP session: the role claim is re-validated against the stored user
row, and every access decision is made by `app.services.rbac` — the same code
path the REST API uses.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from app.db import get_session_factory
from app.errors import ForbiddenError, ValidationError
from app.models import AbsenceType, User
from app.services import absences as absence_service
from app.services import checklist as checklist_service
from app.services import contacts as contacts_service
from app.services import users as users_service


async def _actor(session, user_id: int, role: str) -> User:
    user = await users_service.get_user(session, user_id)
    if user.role.value != role:
        raise ForbiddenError("Роль в запросе не совпадает с ролью пользователя")
    return user


def _absence_payload(request) -> dict[str, Any]:
    return {
        "id": request.id,
        "user_id": request.user_id,
        "type": request.type.value,
        "date_from": request.date_from.isoformat(),
        "date_to": request.date_to.isoformat(),
        "reason": request.reason,
        "status": request.status.value,
        "decided_by": request.decided_by,
    }


def _parse_date(value: str, field: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValidationError(f"{field} должен быть в формате YYYY-MM-DD") from exc


async def absence_create(
    user_id: int,
    role: str,
    type: str,  # noqa: A002 - matches the tool contract
    date_from: str,
    date_to: str,
    reason: str = "",
) -> dict[str, Any]:
    """Создать черновик заявки на отсутствие (отгул / отпуск / больничный)."""
    try:
        absence_type = AbsenceType(type)
    except ValueError as exc:
        raise ValidationError("type: допустимо day_off, vacation, sick") from exc
    start = _parse_date(date_from, "date_from")
    end = _parse_date(date_to, "date_to")

    async with get_session_factory()() as session:
        actor = await _actor(session, user_id, role)
        request = await absence_service.create_draft(
            session, actor, absence_type=absence_type, date_from=start, date_to=end, reason=reason
        )
        return _absence_payload(request)


async def absence_status(user_id: int, role: str, request_id: int) -> dict[str, Any]:
    """Показать статус заявки на отсутствие."""
    async with get_session_factory()() as session:
        actor = await _actor(session, user_id, role)
        request = await absence_service.get_for_actor(session, actor, request_id)
        return _absence_payload(request)


async def absence_list(user_id: int, role: str) -> dict[str, Any]:
    """Список заявок: свои — для стажёра, подопечные/команда — для остальных ролей."""
    async with get_session_factory()() as session:
        actor = await _actor(session, user_id, role)
        requests = await absence_service.list_for_actor(session, actor)
        return {"count": len(requests), "items": [_absence_payload(r) for r in requests]}


async def checklist_get(
    user_id: int, role: str, target_user_id: int | None = None
) -> dict[str, Any]:
    """Чек-лист адаптации с прогрессом (RBAC: свой / подопечного / команды)."""
    async with get_session_factory()() as session:
        actor = await _actor(session, user_id, role)
        target = (
            await users_service.get_user(session, target_user_id)
            if target_user_id is not None
            else await users_service.first_intern(session, actor)
        )
        entries = await checklist_service.get_checklist_for_actor(session, actor, target)
        done, total, next_entry = checklist_service.summarize(entries)
        return {
            "user_id": target.id,
            "full_name": target.full_name,
            "done": done,
            "total": total,
            "next": next_entry.item.title if next_entry else None,
            "items": [
                {
                    "id": entry.item.id,
                    "week": entry.item.week,
                    "title": entry.item.title,
                    "status": entry.status.value,
                }
                for entry in entries
            ],
        }


async def checklist_complete(user_id: int, role: str, item_id: int) -> dict[str, Any]:
    """Отметить пункт чек-листа выполненным (или снять отметку)."""
    async with get_session_factory()() as session:
        actor = await _actor(session, user_id, role)
        progress = await checklist_service.complete_item(session, actor, item_id)
        await session.commit()
        return {"item_id": item_id, "status": progress.status.value}


async def contacts_lookup(user_id: int, role: str, query: str = "") -> dict[str, Any]:
    """К кому обратиться: наставник, руководитель, HR BP команды."""
    async with get_session_factory()() as session:
        actor = await _actor(session, user_id, role)
        rows = await contacts_service.list_contacts(session, actor, query or None)
        return {
            "count": len(rows),
            "items": [{"name": row.name, "role": row.role, "email": row.email} for row in rows],
        }


TOOLS = (
    absence_create,
    absence_status,
    absence_list,
    checklist_get,
    checklist_complete,
    contacts_lookup,
)
