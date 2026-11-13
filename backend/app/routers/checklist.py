from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.deps import get_current_user
from app.models import ProgressStatus, User
from app.schemas import ChecklistItemOut, ChecklistNextOut, ChecklistOut
from app.services import audit
from app.services import checklist as checklist_service
from app.services import users as users_service

router = APIRouter(tags=["checklist"])


def _entry_to_out(entry: checklist_service.ChecklistEntry) -> ChecklistItemOut:
    return ChecklistItemOut(
        id=entry.item.id,
        week=entry.item.week,
        title=entry.item.title,
        description=entry.item.description,
        status=entry.status,
    )


def _to_out(entries: list[checklist_service.ChecklistEntry]) -> ChecklistOut:
    # `next_item` is computed here, not in the client: it is the first pending item by
    # (week, position), and both the UI and the agent must agree on it.
    following = checklist_service.next_item(entries)
    return ChecklistOut(
        items=[_entry_to_out(entry) for entry in entries],
        next_item=(
            ChecklistNextOut(
                id=following.item.id, title=following.item.title, week=following.item.week
            )
            if following
            else None
        ),
        done_count=sum(1 for entry in entries if entry.status is ProgressStatus.done),
        total=len(entries),
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
    return _to_out(entries)


@router.post("/checklist/{item_id}/complete", response_model=ChecklistItemOut)
async def complete_checklist_item(
    item_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ChecklistItemOut:
    entry = await checklist_service.complete_item(session, user, item_id)
    await audit.log(
        session,
        user.id,
        "checklist.completed" if entry.status is ProgressStatus.done else "checklist.reopened",
        {"item_id": item_id, "status": entry.status.value},
    )
    await session.commit()
    return _entry_to_out(entry)
