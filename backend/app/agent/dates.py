"""Local (Europe/Moscow) date resolution for agent actions.

A chat phrase like «оформи отгул завтра» must land on the date the *user* means,
not on the server's UTC date: at 00:30 Moscow the UTC clock still shows yesterday.
Everything the agent derives from "today" goes through `local_today()`.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

MOSCOW = ZoneInfo("Europe/Moscow")

# Relative words a user (or a model imitating one) puts into `date_from`/`date_to`.
RELATIVE_DAYS: dict[str, int] = {
    "сегодня": 0,
    "завтра": 1,
    "послезавтра": 2,
}


def local_now() -> datetime:
    """Now, in the server's business timezone (Europe/Moscow)."""
    return datetime.now(MOSCOW)


def local_today(now: datetime | None = None) -> date:
    """Today's date in Europe/Moscow.

    `now` is accepted for tests: a timezone-aware value is converted to Moscow,
    a naive one is read as Moscow local time. UTC is never used implicitly.
    """
    if now is None:
        return local_now().date()
    if now.tzinfo is None:
        now = now.replace(tzinfo=MOSCOW)
    return now.astimezone(MOSCOW).date()


def parse_date_phrase(value: str, *, today: date | None = None) -> date | None:
    """`«завтра»` / `«послезавтра»` / `«сегодня»` / ISO date → `date`, else None."""
    text = (value or "").strip().lower()
    if not text:
        return None
    base = today or local_today()
    if text in RELATIVE_DAYS:
        return base + timedelta(days=RELATIVE_DAYS[text])
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def utc_midnight_of(day: date) -> datetime:
    """Moscow midnight of `day` as an aware UTC timestamp (audit/debug helpers)."""
    return datetime(day.year, day.month, day.day, tzinfo=MOSCOW).astimezone(UTC)
