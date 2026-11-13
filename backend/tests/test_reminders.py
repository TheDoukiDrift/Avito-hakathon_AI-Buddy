"""S3: the AI-cron imitation, reminders API and deduplication.

Time is never mocked: every function takes `now`.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.db import get_session_factory
from app.models import (
    AuditEvent,
    ChecklistItem,
    ChecklistProgress,
    ProgressStatus,
    Reminder,
    Role,
    User,
)
from app.security import hash_password
from app.services import checklist as checklist_service
from app.services import reminder_cron
from app.services import reminders as reminders_service
from tests.conftest import HR_BP, INTERN, MENTOR, auth_headers

NOW = datetime(2026, 11, 13, 12, 0, tzinfo=UTC)


async def _set_started_at(days_ago: float, *, limit: int | None = None) -> list[int]:
    """Backdate every (or the first `limit`) progress row of the seeded intern."""
    async with get_session_factory()() as session:
        rows = list((await session.execute(select(ChecklistProgress))).scalars())
        if limit is not None:
            rows = rows[:limit]
        for row in rows:
            row.started_at = NOW - timedelta(days=days_ago)
        await session.commit()
        return [row.item_id for row in rows]


async def test_cron_creates_reminders_only_for_overdue_items():
    # Three items started 3 days ago, the rest are fresh: only the overdue three are due.
    async with get_session_factory()() as session:
        all_rows = list((await session.execute(select(ChecklistProgress))).scalars())
        for row in all_rows:
            row.started_at = NOW - timedelta(hours=1)
        for row in all_rows[:3]:
            row.started_at = NOW - timedelta(days=3)
        await session.commit()

    created = await reminder_cron.run_once(now=NOW, overdue_days=2)
    assert len(created) == 3
    assert all("неделя" in reminder.message for reminder in created)
    assert all(reminder.user_id for reminder in created)

    # A second tick with unchanged data must not duplicate anything.
    assert await reminder_cron.run_once(now=NOW, overdue_days=2) == []

    async with get_session_factory()() as session:
        stored = list((await session.execute(select(Reminder))).scalars())
        actions = list((await session.execute(select(AuditEvent.action))).scalars())
    assert len(stored) == 3
    assert actions.count("reminder.created") == 3


async def test_cron_ignores_done_and_fresh_items():
    async with get_session_factory()() as session:
        rows = list((await session.execute(select(ChecklistProgress))).scalars())
        rows[0].started_at = NOW - timedelta(days=10)
        rows[0].status = ProgressStatus.done
        rows[1].started_at = NOW - timedelta(hours=2)
        await session.commit()

    assert await reminder_cron.run_once(now=NOW, overdue_days=2) == []


async def test_ack_then_cron_may_remind_again():
    await _set_started_at(5, limit=1)
    created = await reminder_cron.run_once(now=NOW, overdue_days=2)
    assert len(created) == 1
    reminder_id = created[0].id

    # Acknowledged -> invisible, and the cron is allowed to create a fresh one for
    # the still-pending item.
    async with get_session_factory()() as session:
        owner = await session.get(User, created[0].user_id)
        await reminders_service.ack(session, owner, reminder_id)
        await session.commit()

    again = await reminder_cron.run_once(now=NOW, overdue_days=2)
    assert [reminder.checklist_item_id for reminder in again] == [created[0].checklist_item_id]

    async with get_session_factory()() as session:
        visible = await reminders_service.messages_for(session, created[0].user_id)
    assert len(visible) == 1


async def test_reminders_api_lists_and_acks(client):
    await _set_started_at(4, limit=2)
    created = await reminder_cron.run_once(now=NOW, overdue_days=2)
    headers = await auth_headers(client, INTERN)

    listed = (await client.get("/api/reminders", headers=headers)).json()
    assert len(listed["reminders"]) == 2
    first = listed["reminders"][0]
    assert set(first) == {"id", "checklist_item_id", "message", "created_at"}
    assert created  # sanity: the cron produced them

    acked = await client.post(f"/api/reminders/{first['id']}/ack", headers=headers)
    assert acked.status_code == 200
    assert acked.json() == {"id": first["id"], "acked": True}

    after = (await client.get("/api/reminders", headers=headers)).json()
    assert [item["id"] for item in after["reminders"]] == [
        item["id"] for item in listed["reminders"][1:]
    ]


async def test_mentor_sees_team_reminders_but_not_another_team(client):
    await _set_started_at(4, limit=1)
    created = await reminder_cron.run_once(now=NOW, overdue_days=2)

    mentor_headers = await auth_headers(client, MENTOR)
    mentor_view = (await client.get("/api/reminders", headers=mentor_headers)).json()
    assert [item["id"] for item in mentor_view["reminders"]] == [created[0].id]

    hr_headers = await auth_headers(client, HR_BP)
    hr_view = (await client.get("/api/reminders", headers=hr_headers)).json()
    assert created[0].id in {item["id"] for item in hr_view["reminders"]}

    # A reminder that belongs to somebody outside the mentor's team is not theirs.
    async with get_session_factory()() as session:
        outsider = User(
            email="outsider@example.com",
            password_hash=hash_password("test1234"),
            role=Role.intern,
            full_name="Чужой Стажёров",
            team="Другая команда",
        )
        session.add(outsider)
        await session.flush()
        item = (
            await session.execute(select(ChecklistItem).order_by(ChecklistItem.id).limit(1))
        ).scalar_one()
        foreign = Reminder(user_id=outsider.id, checklist_item_id=item.id, message="чужое")
        session.add(foreign)
        await session.commit()
        foreign_id = foreign.id

    denied = await client.post(f"/api/reminders/{foreign_id}/ack", headers=mentor_headers)
    assert denied.status_code == 403

    intern_headers = await auth_headers(client, INTERN)
    intern_view = (await client.get("/api/reminders", headers=intern_headers)).json()
    assert foreign_id not in {item["id"] for item in intern_view["reminders"]}


async def test_ack_unknown_reminder_is_404(client):
    headers = await auth_headers(client, INTERN)
    response = await client.post("/api/reminders/424242/ack", headers=headers)
    assert response.status_code == 404


async def test_reminders_require_auth(client):
    assert (await client.get("/api/reminders")).status_code == 401
    assert (await client.post("/api/reminders/1/ack")).status_code == 401


async def test_cron_loop_ticks_then_stops():
    await _set_started_at(4, limit=1)
    stop = asyncio.Event()
    task = asyncio.create_task(reminder_cron.cron_loop(stop, interval=0.01))
    await asyncio.sleep(0.05)
    stop.set()
    await asyncio.wait_for(task, timeout=2)

    async with get_session_factory()() as session:
        assert len(list((await session.execute(select(Reminder))).scalars())) == 1


def test_next_item_is_chosen_by_week_then_position():
    # Position order deliberately disagrees with week order: week wins.
    late_week = ChecklistItem(week=1, title="Неделя 1", position=9)
    early_week = ChecklistItem(week=2, title="Неделя 2", position=1)
    entries = [
        checklist_service.ChecklistEntry(late_week, ProgressStatus.pending, None),
        checklist_service.ChecklistEntry(early_week, ProgressStatus.pending, None),
    ]
    assert checklist_service.next_item(entries) is entries[0]
    assert checklist_service.summarize(entries)[2] is entries[0]


async def test_next_item_skips_done_items(client):
    headers = await auth_headers(client, INTERN)
    body = (await client.get("/api/checklist", headers=headers)).json()
    first = body["items"][0]
    assert body["next_item"] == {"id": first["id"], "title": first["title"], "week": 1}

    await client.post(f"/api/checklist/{first['id']}/complete", headers=headers)
    after = (await client.get("/api/checklist", headers=headers)).json()
    assert after["next_item"]["id"] == body["items"][1]["id"]
    assert after["done_count"] == 1
    assert after["total"] == 11
