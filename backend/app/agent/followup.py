"""Deterministic additions both LLM paths must produce (S3 next step, S4 routing).

Nothing here is model output: the next checklist item, the overdue reminders and
the contact to ask are read from the services layer and appended to whatever the
model streamed, so the offline stub and a real provider behave the same.
"""

from __future__ import annotations

from app.agent.base import AgentContext, ContactSnapshot

CHECKLIST_MARKERS = (
    "чек-лист",
    "чеклист",
    "что дальше",
    "следующий шаг",
    "следующ",
)


def is_next_step_question(message: str) -> bool:
    text = message.strip().lower()
    return any(marker in text for marker in CHECKLIST_MARKERS)


def contact_line(contact: ContactSnapshot) -> str:
    return (
        "Не нашёл в базе знаний. По этому вопросу лучше обратиться к "
        f"{contact.name} ({contact.role}), {contact.email}"
    )


def next_step_note(context: AgentContext) -> str:
    """«Следующий шаг» + overdue reminders, from the context snapshot."""
    if not context.checklist:
        return ""
    lines: list[str] = []
    pending = context.next_pending
    if pending is not None:
        lines.append(f"Следующий шаг — «{pending.title}» (неделя {pending.week}).")
    else:
        lines.append("Все пункты чек-листа выполнены — можно переходить к итоговой встрече.")
    if context.reminders:
        lines.append("Просроченные напоминания:")
        lines.extend(f"— {message}" for message in context.reminders)
    return "\n".join(lines)
