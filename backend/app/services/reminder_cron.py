"""The AI-cron imitation of S3: a background loop that owes reminders.

Two entry points, one core:

- `cron_loop()` — started from the FastAPI lifespan, wakes every
  `REMINDER_INTERVAL_SEC` (default 300) and creates what is due.
- `python -m app.services.reminder_cron` — one shot, for tests and demos
  (`REMINDER_OVERDUE_DAYS=0` makes every pending item due immediately).
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime

from app.config import get_settings
from app.db import dispose_engine, get_engine, get_session_factory
from app.models import Base, Reminder
from app.services import reminders as reminders_service

logger = logging.getLogger(__name__)


async def run_once(
    *, now: datetime | None = None, overdue_days: int | None = None
) -> list[Reminder]:
    """One cron tick in its own session; commit only if it produced something."""
    async with get_session_factory()() as session:
        created = await reminders_service.create_due_reminders(
            session, now=now, overdue_days=overdue_days
        )
        if created:
            await session.commit()
            logger.info("reminder cron: создано напоминаний — %s", len(created))
        return created


async def cron_loop(stop_event: asyncio.Event, interval: float | None = None) -> None:
    """Tick immediately, then wait `interval` seconds or until shutdown."""
    seconds = interval if interval is not None else get_settings().reminder_interval_sec
    while not stop_event.is_set():
        try:
            await run_once()
        except Exception:  # noqa: BLE001 - a cron tick must never kill the API process
            logger.exception("reminder cron: тик завершился ошибкой")
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=seconds)
        except TimeoutError:
            continue


async def _main() -> int:
    async with get_engine().begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    try:
        return len(await run_once())
    finally:
        await dispose_engine()


def main() -> None:
    print(json.dumps({"created": asyncio.run(_main())}, ensure_ascii=False))


if __name__ == "__main__":  # pragma: no cover - exercised through `main()`
    main()
