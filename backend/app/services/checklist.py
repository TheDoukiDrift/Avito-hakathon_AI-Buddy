"""Checklist read/complete, shared by the REST router and the MCP tools."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import ConflictError, ForbiddenError, NotFoundError
from app.models import ChecklistItem, ChecklistProgress, ProgressStatus, User
from app.services import rbac


@dataclass
class ChecklistEntry:
    item: ChecklistItem
    status: ProgressStatus
    completed_at: datetime | None


async def _progress_map(session: AsyncSession, user_id: int) -> dict[int, ChecklistProgress]:
    result = await session.execute(
        select(ChecklistProgress).where(ChecklistProgress.user_id == user_id)
    )
    return {row.item_id: row for row in result.scalars()}


async def get_checklist(session: AsyncSession, target: User) -> list[ChecklistEntry]:
    """All items of the active template with the target user's progress.

    Ordered by `(week, position)` — the same order `next_item` (S3) promises, so the
    REST endpoint, the MCP tool and the agent agree on "what's next".
    """
    items = list(
        (
            await session.execute(
                select(ChecklistItem).order_by(ChecklistItem.week, ChecklistItem.position)
            )
        ).scalars()
    )
    progress = await _progress_map(session, target.id)
    entries: list[ChecklistEntry] = []
    for item in items:
        row = progress.get(item.id)
        entries.append(
            ChecklistEntry(
                item=item,
                status=row.status if row else ProgressStatus.pending,
                completed_at=row.completed_at if row else None,
            )
        )
    return entries


async def get_checklist_for_actor(
    session: AsyncSession, actor: User, target: User
) -> list[ChecklistEntry]:
    if not rbac.can_view_checklist(actor, target):
        raise ForbiddenError("Чек-лист другого сотрудника недоступен вашей роли")
    return await get_checklist(session, target)


async def complete_item(
    session: AsyncSession, actor: User, item_id: int, target: User | None = None
) -> ChecklistEntry:
    """Toggle an item on the *target* user's checklist.

    The matrix grants completion of one's own checklist only, and only to an intern
    (mentors/managers/HR BP get read-only visibility of their wards). The guard is
    checked against the real target, not against the actor twice.

    The plan is sequential: an item may be completed only when every earlier item
    (by `week`, then `position`) is already done. Un-completing is always allowed,
    so the intern can step back and redo a week.
    """
    item = await session.get(ChecklistItem, item_id)
    if item is None:
        raise NotFoundError("Пункт чек-листа не найден")
    target = target or actor
    if not rbac.can_complete_checklist(actor, target):
        raise ForbiddenError("Отмечать пункты может только стажёр в своём чек-листе")

    entries = await get_checklist(session, target)
    index = next(i for i, entry in enumerate(entries) if entry.item.id == item_id)
    if entries[index].status is not ProgressStatus.done:
        blocking = next(
            (entry for entry in entries[:index] if entry.status is not ProgressStatus.done),
            None,
        )
        if blocking is not None:
            raise ConflictError(f"Сначала выполните предыдущий шаг: {blocking.item.title}")

    result = await session.execute(
        select(ChecklistProgress).where(
            ChecklistProgress.user_id == target.id, ChecklistProgress.item_id == item_id
        )
    )
    progress = result.scalar_one_or_none()
    if progress is None:
        progress = ChecklistProgress(
            user_id=target.id, item_id=item_id, status=ProgressStatus.pending
        )
        session.add(progress)

    if progress.status is ProgressStatus.done:
        progress.status = ProgressStatus.pending
        progress.completed_at = None
    else:
        progress.status = ProgressStatus.done
        progress.completed_at = datetime.now(UTC)
    await session.flush()
    return ChecklistEntry(item=item, status=progress.status, completed_at=progress.completed_at)


def summarize(entries: list[ChecklistEntry]) -> tuple[int, int, ChecklistEntry | None]:
    """(done, total, next pending entry) — used by the FakeLLM and the dashboard."""
    done = sum(1 for entry in entries if entry.status is ProgressStatus.done)
    next_entry = next((e for e in entries if e.status is ProgressStatus.pending), None)
    return done, len(entries), next_entry


def next_item(entries: list[ChecklistEntry]) -> ChecklistEntry | None:
    """First pending item by `(week, position)` — the S3 `next_item` contract."""
    pending = [entry for entry in entries if entry.status is ProgressStatus.pending]
    if not pending:
        return None
    return min(pending, key=lambda entry: (entry.item.week, entry.item.position))
