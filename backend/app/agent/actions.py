"""Agent actions — the small, honest tool-execution path of the prototype.

The model does not touch the database. It names an action; `execute_action` runs it
through the **services** layer — the same seam the MCP server wraps — so every
ownership/RBAC check is the production one, not a chat-only shortcut.

Both model paths end here: `FakeLLM` derives an action from keywords
(`detect_action`), and `execute_tool_call` turns an OpenAI-style `tool_call` into
the same `AgentAction`, after validating its arguments against the tool schema.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.base import ContactSnapshot, ToolCall
from app.agent.dates import local_today, parse_date_phrase
from app.agent.followup import contact_line
from app.agent.tools import TOOL_TO_ACTION, validate_tool_args
from app.errors import ForbiddenError, NotFoundError, ValidationError
from app.models import AbsenceStatus, AbsenceType, User
from app.services import absences as absence_service
from app.services import checklist as checklist_service
from app.services import contacts as contacts_service
from app.services import reminders as reminders_service
from app.services import users as users_service

ACTION_ABSENCE_CREATE = "absence.create"
ACTION_ABSENCE_CONFIRM = "absence.confirm"
ACTION_ABSENCE_STATUS = "absence.status"
ACTION_ABSENCE_LIST = "absence.list"
ACTION_CHECKLIST_GET = "checklist.get"
ACTION_CHECKLIST_COMPLETE = "checklist.complete"
ACTION_CONTACTS_LOOKUP = "contacts.lookup"
ACTION_CONTACTS_ROUTE = "contacts.route"

ABSENCE_TYPE_LABELS = {
    AbsenceType.day_off: "отгул",
    AbsenceType.vacation: "отпуск",
    AbsenceType.sick: "больничный",
}

ABSENCE_STATUS_LABELS = {
    AbsenceStatus.draft: "черновик",
    AbsenceStatus.pending_approval: "на согласовании",
    AbsenceStatus.approved: "согласована",
    AbsenceStatus.rejected: "отклонена",
}

# Imperative "make it so" verbs. Deliberately NOT matching "оформить"/"подтвердить":
# «как оформить отгул?» must stay an explanation, «оформи отгул завтра» is an action.
_CREATE_RE = re.compile(r"\b(оформи|оформите|создай|создайте|заведи|заведите)\b", re.IGNORECASE)
_CONFIRM_RE = re.compile(r"\b(подтверждаю|подтверди|подтвердите|подтверждаем)\b", re.IGNORECASE)
# The user's explicit yes and nothing else: «подтверждаю», «да, подтверждаю».
_CONFIRM_ONLY_RE = re.compile(r"^\s*(?:да[,.!\s]+)?подтвержда\w*\s*[.!]?\s*$", re.IGNORECASE)
_CHECKLIST_RE = re.compile(r"\b(чек-?лист\w*|чеклист\w*)\b", re.IGNORECASE)
_ROUTING_RE = re.compile(r"\b(к кому|кому|кто занимается)\b", re.IGNORECASE)

_DAY_AFTER_RE = re.compile(r"\b(послезавтра)\b", re.IGNORECASE)
_ISO_DATE_RE = re.compile(r"\b(\d{4}-\d{2}-\d{2})\b")

# Identity is never taken from the model: the authenticated user is the actor.
_IDENTITY_FIELDS = ("user_id", "role")


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
    today = local_today()
    if _DAY_AFTER_RE.search(text):
        return today + timedelta(days=2)
    return today + timedelta(days=1)


def is_confirmation(message: str) -> bool:
    """«подтверждаю» / «да, подтверждаю» — and nothing that asks for another action."""
    return bool(_CONFIRM_ONLY_RE.match(message))


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
        "Проверьте данные и напишите «подтверждаю» — только после этого заявка уйдёт "
        "на согласование.\n\n"
        "Пока ничего не отправлено: черновик виден в панели AbsenceCard."
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
        f"Заявка №{request.id} отправлена на согласование руководителю: {label} "
        f"{_format_date(request.date_from)}, статус pending_approval.\n\n"
        "После руководителя заявку видит HR BP. Статус виден в панели AbsenceCard."
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
    reminder_texts = await reminders_service.messages_for(session, target.id)
    if reminder_texts:
        lines.append("Просроченные напоминания:")
        lines.extend(f"— {message}" for message in reminder_texts)
    return ActionResult(
        text="\n".join(lines),
        data={
            "action": ACTION_CHECKLIST_GET,
            "done": done,
            "total": total,
            "next": next_entry.item.title if next_entry else None,
            "reminders": len(reminder_texts),
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


async def _route_contact(session: AsyncSession, actor: User, args: dict[str, Any]) -> ActionResult:
    contact = await contacts_service.route_question(session, actor.id, args["question"])
    if contact is None:
        return ActionResult(
            text=(
                "В базе знаний есть ответ на этот вопрос — уточните формулировку, я найду материал."
            ),
            data={"action": ACTION_CONTACTS_ROUTE, "contact": None},
        )
    return ActionResult(
        text=contact_line(
            ContactSnapshot(name=contact.name, role=contact.role, email=contact.email)
        ),
        data={
            "action": ACTION_CONTACTS_ROUTE,
            "contact": {"name": contact.name, "role": contact.role, "email": contact.email},
        },
    )


def _describe_absence(request) -> str:
    label = ABSENCE_TYPE_LABELS[request.type]
    status = ABSENCE_STATUS_LABELS[request.status]
    dates = _format_date(request.date_from)
    if request.date_to != request.date_from:
        dates = f"{dates} — {_format_date(request.date_to)}"
    return f"№{request.id}: {label} {dates}, статус {status}"


async def _get_absence_status(
    session: AsyncSession, actor: User, args: dict[str, Any]
) -> ActionResult:
    request = await absence_service.get_for_actor(session, actor, int(args["request_id"]))
    return ActionResult(
        text=f"Заявка {_describe_absence(request)}.",
        data={
            "action": ACTION_ABSENCE_STATUS,
            "request_id": request.id,
            "status": request.status.value,
        },
    )


async def _list_absences(session: AsyncSession, actor: User, args: dict[str, Any]) -> ActionResult:
    requests = await absence_service.list_for_actor(session, actor)
    if not requests:
        return ActionResult(
            text="Заявок пока нет. Скажите даты — подготовлю черновик.",
            data={"action": ACTION_ABSENCE_LIST, "count": 0},
        )
    lines = [f"Заявок: {len(requests)}."]
    lines.extend(f"— {_describe_absence(request)}" for request in requests)
    return ActionResult(
        text="\n".join(lines),
        data={
            "action": ACTION_ABSENCE_LIST,
            "count": len(requests),
            "items": [
                {"request_id": request.id, "status": request.status.value} for request in requests
            ],
        },
    )


async def _complete_checklist(
    session: AsyncSession, actor: User, args: dict[str, Any]
) -> ActionResult:
    entry = await checklist_service.complete_item(session, actor, int(args["item_id"]))
    await session.commit()
    done = entry.status.value == "done"
    text = (
        f"Пункт «{entry.item.title}» отмечен выполненным."
        if done
        else f"Отметка снята с пункта «{entry.item.title}»."
    )
    return ActionResult(
        text=text,
        data={
            "action": ACTION_CHECKLIST_COMPLETE,
            "item_id": entry.item.id,
            "status": entry.status.value,
        },
    )


_EXECUTORS = {
    ACTION_ABSENCE_CREATE: _create_absence,
    ACTION_ABSENCE_CONFIRM: _confirm_absence,
    ACTION_ABSENCE_STATUS: _get_absence_status,
    ACTION_ABSENCE_LIST: _list_absences,
    ACTION_CHECKLIST_GET: _get_checklist,
    ACTION_CHECKLIST_COMPLETE: _complete_checklist,
    ACTION_CONTACTS_LOOKUP: _lookup_contacts,
    ACTION_CONTACTS_ROUTE: _route_contact,
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


def _validation_reply(tool: str, detail: str) -> str:
    """A validation failure is answered in the user's terms, never with a traceback."""
    if tool == "absence_create" and ("date_from" in detail or "date_to" in detail):
        return (
            "Уточните, пожалуйста, дату отсутствия — например «завтра», «послезавтра» "
            "или 2026-11-12 (и причину, если она нужна). Черновик пока не создан."
        )
    return f"Не получилось: {detail}. Действие не выполнено."


async def execute_tool_call(session: AsyncSession, actor: User, call: ToolCall) -> ActionResult:
    """Turn an OpenAI-style `tool_call` into a services call, with the actor as identity.

    `user_id`/`role` from the model are ignored: the authenticated user is the actor,
    so a prompt-injected "create it for user 7" cannot escalate. Relative dates in
    the arguments («завтра») resolve against local Moscow time, not UTC.
    """
    action_name = TOOL_TO_ACTION.get(call.name)
    if action_name is None:
        return ActionResult(
            text=f"Не получилось: неизвестный инструмент {call.name}. Действие не выполнено.",
            data={"tool": call.name, "error": "unknown_tool"},
        )
    try:
        raw = json.loads(call.arguments or "{}")
    except json.JSONDecodeError:
        raw = None
    if not isinstance(raw, dict):
        return ActionResult(
            text="Не получилось: не удалось разобрать аргументы инструмента.",
            data={"tool": call.name, "error": "bad_arguments"},
        )

    args = {key: value for key, value in raw.items() if key not in _IDENTITY_FIELDS}
    args["user_id"] = actor.id
    args["role"] = actor.role.value
    for key in ("date_from", "date_to"):
        value = args.get(key)
        if isinstance(value, str):
            parsed = parse_date_phrase(value)
            if parsed is not None:
                args[key] = parsed.isoformat()

    try:
        validate_tool_args(call.name, args)
    except ValidationError as exc:
        return ActionResult(
            text=_validation_reply(call.name, exc.detail),
            data={"tool": call.name, "error": "validation_error", "detail": exc.detail},
        )
    return await execute_action(session, actor, AgentAction(action_name, args))
