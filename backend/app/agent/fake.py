"""Deterministic offline LLM stub.

The whole prototype must demo without a key (ADR / Q&A 00:53:58), so this is not
a "test double" — it is the default model. Rules are keyword based and read
their facts from `AgentContext`, which the agent fills from the services layer.
"""

from __future__ import annotations

import re
from collections.abc import AsyncIterator, Sequence
from typing import Any

from app.agent.base import AgentContext, ChatTurn

ABSENCE_KEYWORDS = ("отгул", "отпуск", "больничн", "отсутств", "отпроситься", "заявк")
CHECKLIST_KEYWORDS = ("чек-лист", "чеклист", "этап", "шаг", "прогресс", "адаптац")
ROUTING_KEYWORDS = (
    "наставник",
    "руководител",
    "hr",
    "кому",
    "контакт",
    "куратор",
    "кто занимается",
    "к кому",
)

_ROLE_LABELS = {
    "intern": "стажёр",
    "mentor": "наставник",
    "manager": "руководитель",
    "hr_bp": "HR BP",
}

KNOWLEDGE_BASE_NOTE = (
    "Пока в базе знаний (офлайн-заглушка) нет точного ответа на этот вопрос. "
    "Уточните формулировку — или спросите наставника: он отвечает по процессам команды."
)


def _matches(text: str, keywords: Sequence[str]) -> bool:
    return any(keyword in text for keyword in keywords)


def _absence_answer(context: AgentContext) -> str:
    return (
        f"{context.full_name}, оформление отсутствия занимает три шага.\n\n"
        "1. Согласуйте дату с руководителем — это можно сделать неформально, но лучше "
        "до создания заявки.\n"
        "2. Я создам черновик заявки: тип (отгул, отпуск, больничный), даты и причина.\n"
        "3. После вашего подтверждения заявка уходит на согласование: сначала "
        "руководителю, затем HR BP. Сроки — по ТК РФ.\n\n"
        "Черновик можно отозвать или изменить до подтверждения. Скажите даты и причину — "
        "и я подготовлю заявку. Ничего не отправится, пока вы не подтвердите."
    )


def _checklist_answer(context: AgentContext) -> str:
    if not context.checklist:
        return (
            "Чек-лист адаптации ещё не назначен. Обратитесь к наставнику или HR BP — "
            "они подключат вас к программе."
        )
    total = len(context.checklist)
    done = context.done_count
    lines = [f"{context.full_name}, ваш чек-лист адаптации: {done} из {total} выполнено."]
    pending = context.next_pending
    if pending is not None:
        lines.append(f"Ближайший шаг — «{pending.title}» (неделя {pending.week}).")
    else:
        lines.append("Все пункты отмечены выполненными — можно переходить к итоговой встрече.")
    remaining = [item.title for item in context.checklist if not item.done][:3]
    if remaining:
        lines.append("Дальше по плану: " + "; ".join(remaining) + ".")
    lines.append("Отметить пункт выполненным можно в разделе «Мой чек-лист».")
    return "\n".join(lines)


def _routing_answer(context: AgentContext, text: str) -> str:
    if not context.contacts:
        return "Контакты команды пока не заполнены — уточните у HR BP."
    lines = ["По этому вопросу лучше обратиться к:"]
    for contact in context.contacts:
        lines.append(f"— {contact.name}, {contact.role}: {contact.email}")
    if "командиров" in text or "отпуск" in text:
        lines.append("Командировки и отсутствия ведёт HR BP; руководитель согласует даты.")
    lines.append(
        f"Ваша роль — {_ROLE_LABELS.get(context.role.value, context.role.value)}: "
        "данные вне вашей зоны доступа я не показываю."
    )
    return "\n".join(lines)


def answer(message: str, context: AgentContext) -> str:
    """Rule-based answer. Pure function — the unit under test."""
    text = message.strip().lower()
    if _matches(text, ABSENCE_KEYWORDS):
        return _absence_answer(context)
    if _matches(text, CHECKLIST_KEYWORDS):
        return _checklist_answer(context)
    if _matches(text, ROUTING_KEYWORDS):
        return _routing_answer(context, text)
    return KNOWLEDGE_BASE_NOTE


def _chunks(text: str) -> list[str]:
    """Split into word-sized chunks so SSE looks like a real token stream."""
    return [chunk for chunk in re.split(r"(\s+)", text) if chunk]


class FakeLLM:
    """Offline, deterministic, keyword-routed."""

    name = "fake"

    async def stream(
        self,
        messages: Sequence[ChatTurn],
        context: AgentContext,
        tools: Sequence[dict[str, Any]] | None = None,
    ) -> AsyncIterator[str]:
        last_user = next((m.content for m in reversed(messages) if m.role == "user"), "")
        for chunk in _chunks(answer(last_user, context)):
            yield chunk
