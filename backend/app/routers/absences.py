from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.deps import get_current_user
from app.models import User
from app.schemas import AbsenceCreate, AbsenceDecision, AbsenceOut
from app.services import absences as absence_service

router = APIRouter(tags=["absences"])


@router.post("/absences", response_model=AbsenceOut, status_code=201)
async def create_absence(
    payload: AbsenceCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> AbsenceOut:
    """Creates a DRAFT — nothing is sent for approval until the user confirms."""
    request = await absence_service.create_draft(
        session,
        user,
        absence_type=payload.type,
        date_from=payload.date_from,
        date_to=payload.date_to,
        reason=payload.reason,
    )
    return AbsenceOut.model_validate(request)


@router.post("/absences/{request_id}/confirm", response_model=AbsenceOut)
async def confirm_absence(
    request_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> AbsenceOut:
    """User-side confirmation before the action (case requirement for S2)."""
    request = await absence_service.confirm_draft(session, user, request_id)
    return AbsenceOut.model_validate(request)


@router.post("/absences/{request_id}/approve", response_model=AbsenceOut)
async def approve_absence(
    request_id: int,
    payload: AbsenceDecision | None = None,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> AbsenceOut:
    request = await absence_service.decide(
        session, user, request_id, approve=True, comment=payload.comment if payload else None
    )
    return AbsenceOut.model_validate(request)


@router.post("/absences/{request_id}/reject", response_model=AbsenceOut)
async def reject_absence(
    request_id: int,
    payload: AbsenceDecision | None = None,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> AbsenceOut:
    request = await absence_service.decide(
        session, user, request_id, approve=False, comment=payload.comment if payload else None
    )
    return AbsenceOut.model_validate(request)


@router.get("/absences", response_model=list[AbsenceOut])
async def list_absences(
    user_id: int | None = Query(default=None),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[AbsenceOut]:
    requests = await absence_service.list_for_actor(session, user, user_id)
    return [AbsenceOut.model_validate(request) for request in requests]


@router.get("/absences/{request_id}", response_model=AbsenceOut)
async def get_absence(
    request_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> AbsenceOut:
    request = await absence_service.get_for_actor(session, user, request_id)
    return AbsenceOut.model_validate(request)
