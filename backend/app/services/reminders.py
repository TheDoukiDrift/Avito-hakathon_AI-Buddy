"""Reminders for overdue checklist items — the «имитация ИИ-крона» of S3.

The cron is deliberately dumb and predictable: no LLM, no scoring. It looks at
pending checklist rows whose `started_at` is older than N days, creates one text
reminder per (user, item) that has no *unacked* reminder yet, and writes an audit
event. Everything takes an explicit `now`, so tests never patch the clock.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.errors import ForbiddenError, NotFoundError
from app.models import (
    ChecklistItem,
    ChecklistProgress,
    ProgressStatus,
    Reminder,
    Role,
    User,
    utcnow,
)
from app.services import audit

REMINDER_MESSAGE = (
    "Пункт чек-листа «{title}» (неделя {week}) ждёт выполнения уже {days} дн. "
    "Отметьте его в разделе «Мой чек-лист» или напишите наставнику."
)

# How many unacked reminders the agent may quote in one answer.
AGENT_REMINDER_LIMIT = 5


def _aware(value: datetime) -> datetime:
    """SQLite returns naive datetimes; compare them as UTC."""
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def _days_waited(started_at: datetime | None, now: datetime) -> int:
    if started_at is None:
        return 0
    return max((_aware(now) - _aware(started_at)).days, 0)


async def _team_ids(session: AsyncSession, actor: User) -> list[int] | None:
    """Ids of the team's interns; `None` means "no team scope" (see HR BP below)."""
    if actor.role is Role.hr_bp and not actor.team:
        return None
    stmt = select(User.id).where(User.role == Role.intern)
    if actor.team:
        stmt = stmt.where(User.team == actor.team)
    return list((await session.execute(stmt)).scalars())


def _can_view(actor: User, owner: User) -> bool:
    if actor.id == owner.id:
        return True
    if actor.role is Role.intern:
        return False
    return (
        actor.role in (Role.mentor, Role.manager, Role.hr_bp)
        and bool(actor.team)
        and (actor.team == owner.team)
    )


async def create_due_reminders(
    session: AsyncSession,
    *,
    now: datetime | None = None,
    overdue_days: int | None = None,
) -> list[Reminder]:
    """Create the reminders a cron tick owes; returns only the new rows.

    Deduplicated on `(user_id, checklist_item_id)` against *unacked* reminders, so
    a second tick with the same data creates nothing and an acknowledged reminder
    can be followed by a fresh one while the item is still pending.
    """
    settings = get_settings()
    moment = now or utcnow()
    days = settings.reminder_overdue_days if overdue_days is None else overdue_days
    threshold = moment - timedelta(days=days)

    rows = (
        await session.execute(
            select(ChecklistProgress, ChecklistItem)
            .join(ChecklistItem, ChecklistItem.id == ChecklistProgress.item_id)
            .join(User, User.id == ChecklistProgress.user_id)
            .where(
                ChecklistProgress.status == ProgressStatus.pending,
                ChecklistProgress.started_at <= threshold,
                User.role == Role.intern,
            )
            .order_by(ChecklistProgress.user_id, ChecklistItem.week, ChecklistItem.position)
        )
    ).all()

    waiting = {
        (user_id, item_id)
        for user_id, item_id in (
            await session.execute(
                select(Reminder.user_id, Reminder.checklist_item_id).where(
                    Reminder.acked_at.is_(None)
                )
            )
        ).all()
    }

    created: list[Reminder] = []
    for progress, item in rows:
        key = (progress.user_id, item.id)
        if key in waiting:
            continue
        reminder = Reminder(
            user_id=progress.user_id,
            checklist_item_id=item.id,
            message=REMINDER_MESSAGE.format(
                title=item.title, week=item.week, days=_days_waited(progress.started_at, moment)
            ),
        )
        session.add(reminder)
        await session.flush()
        await audit.log(
            session,
            progress.user_id,
            "reminder.created",
            {
                "reminder_id": reminder.id,
                "checklist_item_id": item.id,
                "overdue_days": days,
            },
        )
        waiting.add(key)
        created.append(reminder)
    return created


async def list_for_actor(session: AsyncSession, actor: User) -> list[Reminder]:
    """Unacknowledged reminders: own for an intern, the team's for privileged roles."""
    stmt = select(Reminder).where(Reminder.acked_at.is_(None))
    if actor.role is Role.intern:
        stmt = stmt.where(Reminder.user_id == actor.id)
    else:
        intern_ids = await _team_ids(session, actor)
        if intern_ids is not None:
            stmt = stmt.where(Reminder.user_id.in_(intern_ids))
    stmt = stmt.order_by(Reminder.created_at.desc(), Reminder.id.desc())
    return list((await session.execute(stmt)).scalars())


async def messages_for(session: AsyncSession, user_id: int, limit: int = AGENT_REMINDER_LIMIT):
    """Unacked reminder texts for the agent's next-step answer (oldest first)."""
    stmt = (
        select(Reminder.message)
        .where(Reminder.user_id == user_id, Reminder.acked_at.is_(None))
        .order_by(Reminder.created_at, Reminder.id)
        .limit(limit)
    )
    return list((await session.execute(stmt)).scalars())


async def ack(session: AsyncSession, actor: User, reminder_id: int, *, now: datetime | None = None):
    """Acknowledge a reminder the actor may see; idempotent on a second call."""
    reminder = await session.get(Reminder, reminder_id)
    if reminder is None:
        raise NotFoundError("Напоминание не найдено")
    owner = await session.get(User, reminder.user_id)
    if owner is None or not _can_view(actor, owner):
        raise ForbiddenError("Напоминание другого сотрудника недоступно вашей роли")

    if reminder.acked_at is None:
        reminder.acked_at = now or utcnow()
        await session.flush()
        await audit.log(
            session,
            actor.id,
            "reminder.acked",
            {"reminder_id": reminder.id, "checklist_item_id": reminder.checklist_item_id},
        )
    return reminder


__all__ = [
    "REMINDER_MESSAGE",
    "ack",
    "create_due_reminders",
    "list_for_actor",
    "messages_for",
]
