"""Deterministic offline LLM stub.

The whole prototype must demo without a key (ADR / Q&A 00:53:58), so this is not
a "test double" — it is the default model. Rules are keyword based and read
their facts from `AgentContext`, which the agent fills from the services layer.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Sequence
from typing import Any

from app.agent.actions import AgentAction, detect_action
from app.agent.base import AgentContext, ChatTurn, KbSnippet, split_chunks
from app.agent.followup import contact_line
from app.models import Role

ABSENCE_KEYWORDS = ("отгул", "отпуск", "больничн", "отсутств", "отпроситься", "заявк")
CHECKLIST_KEYWORDS = (
    "чек-лист",
    "чеклист",
    "этап",
    "шаг",
    "прогресс",
    "адаптац",
    "что дальше",
    "следующ",
)
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
    """The same procedure, phrased from the caller's side of the approval chain."""
    if context.role is Role.hr_bp:
        return (
            f"{context.full_name}, вы — финальный контроль: после руководителя заявка "
            "попадает к вам. Стажёр создаёт черновик и подтверждает его, руководитель "
            "согласует или отклоняет даты, и только затем заявка уходит вам на проверку. "
            "Свои собственные заявки вы не согласуете — самосогласования нет."
        )
    if context.role in (Role.mentor, Role.manager):
        return (
            f"{context.full_name}, вы — согласующая сторона: заявка подопечного сначала "
            "уходит вам. Вы видите её в разделе «Заявки» и можете согласовать или отклонить; "
            "после вашего решения заявка уходит в HR BP. Даты подопечный согласует с вами "
            "до создания черновика."
        )
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
        if context.role is not Role.intern:
            return (
                "Чек-лист подопечного ещё не назначен. Программу адаптации подключает HR BP."
            )
        return (
            "Чек-лист адаптации ещё не назначен. Обратитесь к наставнику или HR BP — "
            "они подключат вас к программе."
        )
    total = len(context.checklist)
    done = context.done_count
    privileged = context.role is not Role.intern
    if privileged:
        lines = [f"{context.full_name}, чек-лист подопечного: {done} из {total} выполнено."]
    else:
        lines = [f"{context.full_name}, ваш чек-лист адаптации: {done} из {total} выполнено."]
    pending = context.next_pending
    if pending is not None:
        if privileged:
            lines.append(f"Ближайший шаг подопечного — «{pending.title}» (неделя {pending.week}).")
        else:
            lines.append(f"Ближайший шаг — «{pending.title}» (неделя {pending.week}).")
    elif privileged:
        lines.append("Подопечный прошёл все шаги — можно планировать итоговую встречу.")
    else:
        lines.append("Все пункты отмечены выполненными — можно переходить к итоговой встрече.")
    remaining = [item.title for item in context.checklist if not item.done][:3]
    if remaining:
        lines.append("Дальше по плану: " + "; ".join(remaining) + ".")
    if context.reminders:
        reminder_label = (
            "Просроченные напоминания подопечного:" if privileged else "Просроченные напоминания:"
        )
        lines.append(reminder_label)
        lines.extend(f"— {message}" for message in context.reminders)
    if not privileged:
        lines.append("Отметить пункт выполненным можно в разделе «Мой чек-лист».")
    return "\n".join(lines)


def _routing_answer(context: AgentContext, text: str) -> str:
    contacts = [contact for contact in context.contacts if contact.name != context.full_name]
    if not contacts:
        return "Контакты команды пока не заполнены — уточните у HR BP."
    lines = ["По этому вопросу лучше обратиться к:"]
    for contact in contacts:
        lines.append(f"— {contact.name}, {contact.role}: {contact.email}")
    if "командиров" in text or "отпуск" in text:
        if context.role is Role.intern:
            lines.append("Командировки и отсутствия ведёт HR BP; руководитель согласует даты.")
        elif context.role is Role.hr_bp:
            lines.append("Заявки приходят к вам после руководителя — вы проверяете оформление.")
        else:
            lines.append("Отсутствия подопечных согласуете вы; оформление ведёт HR BP.")
    lines.append(
        f"Ваша роль — {_ROLE_LABELS.get(context.role.value, context.role.value)}: "
        "данные вне вашей зоны доступа я не показываю."
    )
    return "\n".join(lines)


def _fallback_note(context: AgentContext) -> str:
    if context.role is Role.intern:
        return KNOWLEDGE_BASE_NOTE
    if context.role is Role.hr_bp:
        return (
            "Пока в базе знаний (офлайн-заглушка) нет точного ответа на этот вопрос. "
            "Уточните формулировку — или задайте вопрос коллегам в HR."
        )
    return (
        "Пока в базе знаний (офлайн-заглушка) нет точного ответа на этот вопрос. "
        "Уточните формулировку — или задайте вопрос HR BP: он ведёт процессы."
    )


def _excerpt(content: str, title: str, limit: int = 320) -> str:
    """First whole sentences of a chunk, without the repeated title prefix."""
    text = content.strip()
    prefix = f"{title}. "
    if text.startswith(prefix):
        text = text[len(prefix) :]
    if len(text) <= limit:
        return text
    cut = text[:limit]
    boundary = max(cut.rfind(". "), cut.rfind("! "), cut.rfind("? "))
    if boundary > limit // 2:
        cut = cut[: boundary + 1]
    return cut


def _rag_answer(sources: Sequence[KbSnippet]) -> str:
    """Retrieved chunks are the answer — every paragraph names its source document."""
    grouped: dict[str, list[str]] = {}
    order: list[str] = []
    for source in sources:
        excerpt = _excerpt(source.content, source.title)
        if not excerpt:
            continue
        if source.title not in grouped:
            grouped[source.title] = []
            order.append(source.title)
        if excerpt not in grouped[source.title]:
            grouped[source.title].append(excerpt)
    parts = [
        f"{' '.join(grouped[title]).rstrip(' .')} — по материалу «{title}»." for title in order
    ]
    return "\n\n".join(parts) if parts else KNOWLEDGE_BASE_NOTE


def answer(message: str, context: AgentContext, sources: Sequence[KbSnippet] = ()) -> str:
    """Rule-based answer. Pure function — the unit under test."""
    text = message.strip().lower()
    if sources:
        # Procedure docs are written for the intern; for an approver (mentor/manager/
        # HR BP) the backend template is the correct answer even when retrieval hits.
        if context.role is not Role.intern and _matches(text, ABSENCE_KEYWORDS):
            return _absence_answer(context)
        # RAG path: retrieved material wins over keyword shortcuts, so an answer
        # always carries the document it came from.
        return _rag_answer(sources)
    if _matches(text, ABSENCE_KEYWORDS):
        return _absence_answer(context)
    if _matches(text, CHECKLIST_KEYWORDS):
        return _checklist_answer(context)
    if _matches(text, ROUTING_KEYWORDS):
        return _routing_answer(context, text)
    if context.route is not None:
        # S4: the knowledge base had nothing — name the first person of the chain.
        return contact_line(context.route)
    return _fallback_note(context)


class FakeLLM:
    """Offline, deterministic, keyword-routed."""

    name = "fake"

    def plan(self, message: str, context: AgentContext) -> AgentAction | None:
        """The "tool call" of the offline model: a keyword-derived action or None.

        Only `FakeLLM` implements `plan()`; the OpenAI-compatible client reports
        `tool_calls` through `stream_turn()` and the same `execute_action` seam runs
        them (see `loop.py`).
        """
        return detect_action(message)

    async def stream(
        self,
        messages: Sequence[ChatTurn],
        context: AgentContext,
        tools: Sequence[dict[str, Any]] | None = None,
        sources: Sequence[KbSnippet] = (),
    ) -> AsyncIterator[str]:
        last_user = next((m.content for m in reversed(messages) if m.role == "user"), "")
        for chunk in split_chunks(answer(last_user, context, sources)):
            yield chunk
