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
    KbDocument,
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

# (title, content, source_url, keywords) — синтетическая база знаний (ADR-01/ADR-02).
# Содержимое намеренно короткое: прототип показывает retrieve-then-answer, а не
# корпоративную базу. Цифр по ДМС и бенефитам нет — они вне области кейса.
KB_DOCUMENTS: list[tuple[str, str, str, str]] = [
    (
        "Отгул по ТК РФ: процедура",
        "Отгул оформляется заявкой с типом «отгул», датой и причиной. Сначала дату "
        "согласуют с руководителем, затем заявка уходит на согласование руководителю, "
        "при необходимости — HR BP. Черновик можно изменить или отозвать до подтверждения.",
        "https://www.consultant.ru/document/cons_doc_LAW_34683/",
        "отгул отгула отпроситься отсутствие заявка процедура тк рф руководитель",
    ),
    (
        "Доступы Jira и Confluence",
        "Доступы к Jira и Confluence запрашиваются в первый день: заявка на доступ, "
        "согласование руководителя, выдача в течение рабочего дня. Пространство команды "
        "и проект выдаёт администратор Jira, права на редактирование Confluence — владелец "
        "пространства.",
        "https://avito.tech/",
        "jira confluence доступ доступы вики пространство проект права",
    ),
    (
        "Чек-лист новичка: первые недели",
        "Первая неделя — знакомство с командой, цели и план с руководителем, доступы, "
        "техника. Вторая неделя — инструмент отслеживания прогресса. Далее регулярные "
        "встречи 1:1 с наставником, обучение и ревью компетенций.",
        "https://github.com/avito-tech/tech-internship",
        "чек-лист чеклист новичок адаптация стажёр этапы неделя онбординг",
    ),
    (
        "Код-стайл команды",
        "Код-стайл фиксируется линтерами: форматтер и статический анализ в CI. "
        "Спорные правила обсуждаются на ретро и попадают в конфиг репозитория, а не в "
        "устные договорённости. Локальные исключения — только с комментарием в коде.",
        "https://github.com/avito-tech/playbook",
        "код-стайл кодстайл стиль линтер форматтер правила код",
    ),
    (
        "Процесс код-ревью",
        "Изменения проходят через merge request: автор описывает задачу и проверку, "
        "ревьюер отвечает в течение рабочего дня, обязательный минимум — один одобряющий. "
        "Мелкие правки допускаются после апрува, крупные — новым ревью.",
        "https://github.com/avito-tech/playbook",
        "ревью код-ревью ревьюер merge request мр апрув проверка изменения",
    ),
    (
        "Grafana: первые шаги",
        "Дашборды команды живут в общем пространстве Grafana. Новичку выдаётся доступ на "
        "чтение; редактирование — через заявку на доступ к папке команды. Метрики сервиса "
        "находятся по имени сервиса, алерты настраивает дежурный.",
        "https://avito.tech/",
        "grafana графана дашборд метрики мониторинг алерты дежурный",
    ),
    (
        "ДМС: куда обратиться",
        "Вопросы добровольного медицинского страхования ведёт HR BP: он подскажет "
        "порядок обращения и список доступных опций. Конкретные условия и цифры "
        "обсуждаются индивидуально и в базе знаний не публикуются.",
        "https://avito.tech/",
        "дмс страхование медицина полис врач hr",
    ),
    (
        "Встречи 1:1 и обратная связь",
        "Встречи 1:1 с наставником проходят раз в неделю: итоги недели, блокеры, "
        "обратная связь. Конспект ведётся в общем документе команды, решения фиксируются "
        "задачами. Просить встречу можно в любой момент, а не только по расписанию.",
        "https://github.com/avito-tech/playbook",
        "1:1 встреча наставник обратная связь фидбек конспект блокеры",
    ),
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


async def _ensure_kb_documents(session: AsyncSession) -> int:
    existing = {row.title for row in (await session.execute(select(KbDocument))).scalars()}
    added = 0
    for title, content, source_url, keywords in KB_DOCUMENTS:
        if title not in existing:
            session.add(
                KbDocument(title=title, content=content, source_url=source_url, keywords=keywords)
            )
            added += 1
    return added


async def seed(session: AsyncSession) -> dict[str, int]:
    """Create anything missing, touch nothing that exists."""
    users = {}
    for email, role, full_name in USERS:
        users[email] = await _ensure_user(session, email, role, full_name)

    template = await _ensure_template(session)
    items = await _ensure_items(session, template)
    await _ensure_progress(session, users["intern@example.com"], items)
    await _ensure_contacts(session)
    await _ensure_kb_documents(session)
    await session.commit()

    return {
        "users": len(users),
        "checklist_items": len(items),
        "contacts": len(CONTACTS),
        "kb_documents": len(KB_DOCUMENTS),
    }


async def main() -> dict[str, int]:
    async with get_engine().begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with get_session_factory()() as session:
        summary = await seed(session)
    await dispose_engine()
    return summary


if __name__ == "__main__":
    print(asyncio.run(main()))
