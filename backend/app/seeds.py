"""Idempotent seed data.

Run with `python -m app.seeds` (entrypoint.sh does it on container start).
Synthetic people, real adaptation structure (ADR-13).
"""

from __future__ import annotations

import asyncio

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import dispose_engine, get_engine, get_session_factory
from app.models import (
    Base,
    ChecklistItem,
    ChecklistProgress,
    ChecklistTemplate,
    Contact,
    ProgressStatus,
    Role,
    User,
)
from app.security import hash_password

TEST_PASSWORD = "test1234"
TEAM = "Platform"

USERS: list[tuple[str, Role, str]] = [
    ("intern@example.com", Role.intern, "Доуки Хоши"),
    ("mentor@example.com", Role.mentor, "Иван Наставников"),
    ("manager@example.com", Role.manager, "Мария Руководителева"),
    ("hr.bp@example.com", Role.hr_bp, "Ольга ЭйчАр"),
]

# (week, title, description) — ADR-13: week 1 onboarding, week 2 progress tool, then the
# regular mentor cadence up to graduation.
CHECKLIST_ITEMS: list[tuple[int, str, str]] = [
    (
        1,
        "Знакомство с командой",
        "Познакомься с командой, добавься в ключевые чаты и каналы команды.",
    ),
    (
        1,
        "Цели и план с руководителем",
        "Обсуди с руководителем цели, план адаптации, критерии успеха и OKR команды.",
    ),
    (
        1,
        "Доступы Jira и Confluence",
        "Запроси и проверь доступы к Jira, Confluence и пространству своего кластера.",
    ),
    (
        1,
        "Получение техники",
        "Получи ноутбук и доступы к рабочему окружению, проверь VPN.",
    ),
    (
        2,
        "Запрос инструмента прогресса у куратора",
        "Запроси у куратора стажировки инструмент отслеживания прогресса.",
    ),
    (
        2,
        "Внесение целей, задач и ожиданий",
        "Внеси в инструмент прогресса цели, задачи и ожидания от стажировки.",
    ),
    (3, "1:1 с наставником", "Назначь регулярные встречи 1:1 и заведи конспект встреч."),
    (4, "Обучение", "Пройди обязательные курсы и изучи документы команды."),
    (8, "Ревью компетенций", "Пройди промежуточное ревью компетенций с наставником."),
    (12, "Экваторная встреча", "Подготовь презентацию промежуточных результатов и выступи."),
    (24, "Выпускной", "Защити итоговые результаты стажировки."),
]

CONTACTS: list[tuple[str, str, str]] = [
    ("Иван Наставников", "наставник", "mentor@example.com"),
    ("Мария Руководителева", "руководитель", "manager@example.com"),
    ("Ольга ЭйчАр", "HR BP", "hr.bp@example.com"),
]


async def _ensure_user(session: AsyncSession, email: str, role: Role, full_name: str) -> User:
    existing = (await session.execute(select(User).where(User.email == email))).scalar_one_or_none()
    if existing is not None:
        return existing
    user = User(
        email=email,
        password_hash=hash_password(TEST_PASSWORD),
        role=role,
        full_name=full_name,
        team=TEAM,
    )
    session.add(user)
    await session.flush()
    return user


async def _ensure_template(session: AsyncSession) -> ChecklistTemplate:
    template = (
        await session.execute(
            select(ChecklistTemplate).where(ChecklistTemplate.name == "Адаптация стажёра")
        )
    ).scalar_one_or_none()
    if template is None:
        template = ChecklistTemplate(
            name="Адаптация стажёра",
            description="Чек-лист первых недель: онбординг, прогресс, регулярные встречи.",
        )
        session.add(template)
        await session.flush()
    return template


async def _ensure_items(session: AsyncSession, template: ChecklistTemplate) -> list[ChecklistItem]:
    existing = {
        item.title: item
        for item in (
            await session.execute(
                select(ChecklistItem).where(ChecklistItem.template_id == template.id)
            )
        ).scalars()
    }
    items: list[ChecklistItem] = []
    for position, (week, title, description) in enumerate(CHECKLIST_ITEMS, start=1):
        item = existing.get(title)
        if item is None:
            item = ChecklistItem(
                template_id=template.id,
                week=week,
                title=title,
                description=description,
                position=position,
            )
            session.add(item)
            await session.flush()
        items.append(item)
    return items


async def _ensure_progress(session: AsyncSession, intern: User, items: list[ChecklistItem]) -> None:
    existing = {
        row.item_id
        for row in (
            await session.execute(
                select(ChecklistProgress).where(ChecklistProgress.user_id == intern.id)
            )
        ).scalars()
    }
    for item in items:
        if item.id not in existing:
            session.add(
                ChecklistProgress(user_id=intern.id, item_id=item.id, status=ProgressStatus.pending)
            )


async def _ensure_contacts(session: AsyncSession) -> None:
    existing = {contact.email for contact in (await session.execute(select(Contact))).scalars()}
    for name, role, email in CONTACTS:
        if email not in existing:
            session.add(Contact(name=name, role=role, team=TEAM, email=email))


async def seed(session: AsyncSession) -> dict[str, int]:
    """Create anything missing, touch nothing that exists."""
    users = {}
    for email, role, full_name in USERS:
        users[email] = await _ensure_user(session, email, role, full_name)

    template = await _ensure_template(session)
    items = await _ensure_items(session, template)
    await _ensure_progress(session, users["intern@example.com"], items)
    await _ensure_contacts(session)
    await session.commit()

    return {"users": len(users), "checklist_items": len(items), "contacts": len(CONTACTS)}


async def main() -> dict[str, int]:
    async with get_engine().begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with get_session_factory()() as session:
        summary = await seed(session)
    await dispose_engine()
    return summary


if __name__ == "__main__":
    print(asyncio.run(main()))
