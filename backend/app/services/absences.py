"""Absence requests — ADR-12 lifecycle: draft → pending_approval → approved/rejected.

The two approval hops (manager, then HR BP) are modelled as "any approver may
decide"; the UI shows the chain and the audit trail keeps both steps.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import ForbiddenError, NotFoundError, ValidationError
from app.models import AbsenceRequest, AbsenceStatus, Role, User
from app.services import audit, rbac


async def create_draft(
    session: AsyncSession,
    actor: User,
    *,
    absence_type,
    date_from,
    date_to,
    reason: str | None,
) -> AbsenceRequest:
    if date_to < date_from:
        raise ValidationError("Дата окончания не может быть раньше даты начала")
    request = AbsenceRequest(
        user_id=actor.id,
        type=absence_type,
        date_from=date_from,
        date_to=date_to,
        reason=reason,
        status=AbsenceStatus.draft,
    )
    session.add(request)
    await session.flush()
    await audit.log(
        session,
        actor.id,
        "absence.created",
        {"request_id": request.id, "type": absence_type.value, "status": "draft"},
    )
    await session.commit()
    await session.refresh(request)
    return request


async def get_request(session: AsyncSession, request_id: int) -> AbsenceRequest:
    request = await session.get(AbsenceRequest, request_id)
    if request is None:
        raise NotFoundError("Заявка не найдена")
    return request


async def confirm_draft(session: AsyncSession, actor: User, request_id: int) -> AbsenceRequest:
    """The user confirms their own draft — the "подтверждение перед действием" step."""
    request = await get_request(session, request_id)
    if request.user_id != actor.id:
        raise ForbiddenError("Подтвердить можно только собственную заявку")
    if request.status is not AbsenceStatus.draft:
        raise ValidationError("Подтвердить можно только черновик заявки")
    request.status = AbsenceStatus.pending_approval
    await audit.log(
        session, actor.id, "absence.confirmed", {"request_id": request.id, "status": "pending"}
    )
    await session.commit()
    await session.refresh(request)
    return request


async def decide(
    session: AsyncSession,
    actor: User,
    request_id: int,
    *,
    approve: bool,
    comment: str | None = None,
) -> AbsenceRequest:
    request = await get_request(session, request_id)
    owner = await session.get(User, request.user_id)
    if owner is None:  # pragma: no cover - FK guarantees it
        raise NotFoundError("Владелец заявки не найден")
    if not rbac.can_approve_absence(actor, owner):
        raise ForbiddenError("Согласовывать заявки этой роли запрещено")
    if request.status is not AbsenceStatus.pending_approval:
        raise ValidationError("Согласовать можно только заявку в статусе pending_approval")

    request.status = AbsenceStatus.approved if approve else AbsenceStatus.rejected
    request.decided_by = actor.id
    request.decided_at = datetime.now(UTC)
    await audit.log(
        session,
        actor.id,
        "absence.approved" if approve else "absence.rejected",
        {"request_id": request.id, "comment": comment or ""},
    )
    await session.commit()
    await session.refresh(request)
    return request


async def list_for_actor(
    session: AsyncSession, actor: User, target_user_id: int | None = None
) -> list[AbsenceRequest]:
    stmt = select(AbsenceRequest).join(User, User.id == AbsenceRequest.user_id)

    if target_user_id is not None and target_user_id != actor.id:
        target = await session.get(User, target_user_id)
        if target is None:
            raise NotFoundError("Пользователь не найден")
        if not rbac.can_view_absence(actor, target):
            raise ForbiddenError("Заявки другого сотрудника недоступны вашей роли")
        stmt = stmt.where(AbsenceRequest.user_id == target.id)
    elif actor.role is Role.intern or target_user_id == actor.id:
        stmt = stmt.where(AbsenceRequest.user_id == actor.id)
    elif actor.role is not Role.hr_bp:
        # mentor / manager: interns of their own team
        stmt = stmt.where(User.role == Role.intern, User.team == actor.team)

    stmt = stmt.order_by(AbsenceRequest.id.desc())
    return list((await session.execute(stmt)).scalars())


async def get_for_actor(session: AsyncSession, actor: User, request_id: int) -> AbsenceRequest:
    request = await get_request(session, request_id)
    owner = await session.get(User, request.user_id)
    if owner is None:  # pragma: no cover
        raise NotFoundError("Владелец заявки не найден")
    if not rbac.can_view_absence(actor, owner):
        raise ForbiddenError("Заявка недоступна вашей роли")
    return request
