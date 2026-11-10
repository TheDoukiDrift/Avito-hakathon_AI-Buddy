from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.deps import get_current_user
from app.models import ProgressStatus, User
from app.schemas import ChecklistItemOut, ChecklistOut
from app.services import audit
from app.services import checklist as checklist_service
from app.services import users as users_service

router = APIRouter(tags=["checklist"])


def _to_out(target: User, entries: list[checklist_service.ChecklistEntry]) -> ChecklistOut:
    items = [
        ChecklistItemOut(
            id=entry.item.id,
            week=entry.item.week,
            title=entry.item.title,
            description=entry.item.description,
            position=entry.item.position,
            status=entry.status,
            completed_at=entry.completed_at,
        )
        for entry in entries
    ]
    done = sum(1 for entry in entries if entry.status is ProgressStatus.done)
    return ChecklistOut(
        user_id=target.id, full_name=target.full_name, done=done, total=len(entries), items=items
    )


@router.get("/checklist", response_model=ChecklistOut)
async def get_checklist(
    user_id: int | None = Query(default=None, description="Чей чек-лист (RBAC проверит права)"),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ChecklistOut:
    target = (
        await users_service.get_user(session, user_id)
        if user_id is not None
        else await users_service.first_intern(session, user)
    )
    entries = await checklist_service.get_checklist_for_actor(session, user, target)
    return _to_out(target, entries)


@router.post("/checklist/{item_id}/complete")
async def complete_checklist_item(
    item_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    progress = await checklist_service.complete_item(session, user, item_id)
    await audit.log(
        session,
        user.id,
        "checklist.completed" if progress.status is ProgressStatus.done else "checklist.reopened",
        {"item_id": item_id, "status": progress.status.value},
    )
    await session.commit()
    return {"item_id": item_id, "status": progress.status.value}
