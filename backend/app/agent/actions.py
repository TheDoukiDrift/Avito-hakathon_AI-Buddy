"""Agent actions — the small, honest tool-execution path of the prototype.

The model does not touch the database. It names an action; `execute_action` runs it
through the **services** layer — the same seam the MCP server wraps — so every
ownership/RBAC check is the production one, not a chat-only shortcut.

`FakeLLM` decides actions with keyword rules (see `detect_action`). The
OpenAI-compatible client receives the same tool schemas, but its streamed
`tool_calls` are not executed yet (scaffold limitation, documented in `loop.py`).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import ForbiddenError, NotFoundError, ValidationError
from app.models import AbsenceType, User
from app.services import absences as absence_service
from app.services import checklist as checklist_service
from app.services import contacts as contacts_service
from app.services import users as users_service

ACTION_ABSENCE_CREATE = "absence.create"
ACTION_ABSENCE_CONFIRM = "absence.confirm"
ACTION_CHECKLIST_GET = "checklist.get"
ACTION_CONTACTS_LOOKUP = "contacts.lookup"

ABSENCE_TYPE_LABELS = {
    AbsenceType.day_off: "отгул",
    AbsenceType.vacation: "отпуск",
    AbsenceType.sick: "больничный",
}

# Imperative "make it so" verbs. Deliberately NOT matching "оформить"/"подтвердить":
# «как оформить отгул?» must stay an explanation, «оформи отгул завтра» is an action.
_CREATE_RE = re.compile(r"\b(оформи|оформите|создай|создайте|заведи|заведите)\b", re.IGNORECASE)
_CONFIRM_RE = re.compile(r"\b(подтверждаю|подтверди|подтвердите|подтверждаем)\b", re.IGNORECASE)
_CHECKLIST_RE = re.compile(r"\b(чек-?лист\w*|чеклист\w*)\b", re.IGNORECASE)
_ROUTING_RE = re.compile(r"\b(к кому|кому|кто занимается)\b", re.IGNORECASE)

_TOMORROW_RE = re.compile(r"\b(завтра)\b", re.IGNORECASE)
_DAY_AFTER_RE = re.compile(r"\b(послезавтра)\b", re.IGNORECASE)
_ISO_DATE_RE = re.compile(r"\b(\d{4}-\d{2}-\d{2})\b")


@dataclass
class AgentAction:
    """A named operation with plain-data arguments (what an LLM tool call carries)."""

    name: str
    args: dict[str, Any] = field(default_factory=dict)


@dataclass
class ActionResult:
    """Text for the user plus the structured payload for the SSE `tool_call` event."""

    text: str
    data: dict[str, Any] = field(default_factory=dict)


def _absence_type(text: str) -> AbsenceType:
    if "отпуск" in text:
        return AbsenceType.vacation
    if "больничн" in text or "болею" in text:
        return AbsenceType.sick
    return AbsenceType.day_off


def _target_date(text: str) -> date:
    match = _ISO_DATE_RE.search(text)
    if match:
        try:
            return date.fromisoformat(match.group(1))
        except ValueError:
            pass
    if _DAY_AFTER_RE.search(text):
        return date.today() + timedelta(days=2)
    return date.today() + timedelta(days=1)


def detect_action(message: str) -> AgentAction | None:
    """Map a user phrase to one action, or None when the message is just a question."""
    text = message.strip()
    lowered = text.lower()

    if _CONFIRM_RE.search(lowered):
        # Confirmation always targets the caller's own latest draft (resolved in the
        # executor), so a chat phrase can never confirm somebody else's request.
        return AgentAction(ACTION_ABSENCE_CONFIRM, {})

    if _CREATE_RE.search(lowered) and any(
        keyword in lowered for keyword in ("отгул", "отпуск", "больничн", "отсутств", "заявк")
    ):
        day = _target_date(lowered)
        return AgentAction(
            ACTION_ABSENCE_CREATE,
            {
                "type": _absence_type(lowered).value,
                "date_from": day.isoformat(),
                "date_to": day.isoformat(),
            },
        )

    if _CHECKLIST_RE.search(lowered):
        return AgentAction(ACTION_CHECKLIST_GET, {})

    if _ROUTING_RE.search(lowered):
        return AgentAction(ACTION_CONTACTS_LOOKUP, {"query": text})

    return None


def _format_date(value: date) -> str:
    return value.isoformat()


async def _create_absence(session: AsyncSession, actor: User, args: dict[str, Any]) -> ActionResult:
    absence_type = AbsenceType(args["type"])
    date_from = date.fromisoformat(args["date_from"])
    date_to = date.fromisoformat(args.get("date_to") or args["date_from"])
    request = await absence_service.create_draft(
        session,
        actor,
        absence_type=absence_type,
        date_from=date_from,
        date_to=date_to,
        reason=args.get("reason"),
    )
    label = ABSENCE_TYPE_LABELS[absence_type]
    text = (
        f"Черновик заявки №{request.id} создан: {label} {_format_date(date_from)}. "
        "Подтвердить?\n\n"
        "Ничего не отправлено: напишите «подтверждаю», и я отправлю заявку на "
        "согласование. Черновик виден в панели AbsenceCard."
    )
    return ActionResult(
        text=text,
        data={
            "action": ACTION_ABSENCE_CREATE,
            "request_id": request.id,
            "status": request.status.value,
            "type": absence_type.value,
            "date_from": _format_date(date_from),
            "date_to": _format_date(date_to),
        },
    )


async def _confirm_absence(
    session: AsyncSession, actor: User, args: dict[str, Any]
) -> ActionResult:
    request_id = args.get("request_id")
    if request_id is None:
        draft = await absence_service.latest_own_draft(session, actor)
        if draft is None:
            return ActionResult(
                text=(
                    "У вас нет черновика, который можно подтвердить. "
                    "Скажите, какой отгул оформить — например: «оформи отгул завтра»."
                ),
                data={"action": ACTION_ABSENCE_CONFIRM, "status": "no_draft"},
            )
        request_id = draft.id

    # `confirm_draft` re-checks ownership: a foreign id is a 403, not a silent success.
    request = await absence_service.confirm_draft(session, actor, int(request_id))
    label = ABSENCE_TYPE_LABELS[request.type]
    text = (
        f"Заявка №{request.id} отправлена на согласование: {label} "
        f"{_format_date(request.date_from)}, статус pending_approval.\n\n"
        "Согласует руководитель, при необходимости — HR BP. Статус виден в панели "
        "AbsenceCard."
    )
    return ActionResult(
        text=text,
        data={
            "action": ACTION_ABSENCE_CONFIRM,
            "request_id": request.id,
            "status": request.status.value,
        },
    )


async def _get_checklist(session: AsyncSession, actor: User, args: dict[str, Any]) -> ActionResult:
    target = actor
    if args.get("target_user_id") is not None:
        target = await users_service.get_user(session, int(args["target_user_id"]))
    entries = await checklist_service.get_checklist_for_actor(session, actor, target)
    done, total, next_entry = checklist_service.summarize(entries)
    lines = [f"Чек-лист: {done} из {total} выполнено."]
    if next_entry is not None:
        lines.append(f"Ближайший шаг — «{next_entry.item.title}» (неделя {next_entry.item.week}).")
    else:
        lines.append("Все пункты отмечены выполненными.")
    return ActionResult(
        text="\n".join(lines),
        data={
            "action": ACTION_CHECKLIST_GET,
            "done": done,
            "total": total,
            "next": next_entry.item.title if next_entry else None,
        },
    )


async def _lookup_contacts(
    session: AsyncSession, actor: User, args: dict[str, Any]
) -> ActionResult:
    rows = await contacts_service.list_contacts(session, actor, args.get("query") or None)
    if not rows:
        return ActionResult(
            text="Контакты команды пока не заполнены — уточните у HR BP.",
            data={"action": ACTION_CONTACTS_LOOKUP, "count": 0},
        )
    lines = ["По этому вопросу лучше обратиться к:"]
    lines.extend(f"— {row.name}, {row.role}: {row.email}" for row in rows)
    return ActionResult(
        text="\n".join(lines),
        data={
            "action": ACTION_CONTACTS_LOOKUP,
            "count": len(rows),
            "items": [{"name": row.name, "role": row.role, "email": row.email} for row in rows],
        },
    )


_EXECUTORS = {
    ACTION_ABSENCE_CREATE: _create_absence,
    ACTION_ABSENCE_CONFIRM: _confirm_absence,
    ACTION_CHECKLIST_GET: _get_checklist,
    ACTION_CONTACTS_LOOKUP: _lookup_contacts,
}


async def execute_action(session: AsyncSession, actor: User, action: AgentAction) -> ActionResult:
    """Run an action through the services layer (RBAC/ownership enforced there)."""
    executor = _EXECUTORS.get(action.name)
    if executor is None:
        raise ValidationError(f"Неизвестное действие: {action.name}")
    try:
        return await executor(session, actor, action.args)
    except (ForbiddenError, NotFoundError, ValidationError) as exc:
        # A denied action is a normal chat outcome, not a 500: explain it and move on.
        return ActionResult(
            text=f"Не получилось: {exc.detail}",
            data={"action": action.name, "error": exc.code},
        )
