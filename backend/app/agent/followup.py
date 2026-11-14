"""Deterministic additions both LLM paths must produce (S3 next step, S4 routing).

Nothing here is model output: the next checklist item, the overdue reminders and
the contact to ask are read from the services layer and appended to whatever the
model streamed, so the offline stub and a real provider behave the same.
"""

from __future__ import annotations

from app.agent.base import AgentContext, ContactSnapshot
from app.models import Role

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
    """«Следующий шаг» + overdue reminders, from the context snapshot.

    For a privileged caller the checklist belongs to their ward, so the note is
    phrased as progress rather than as an instruction to the caller.
    """
    if not context.checklist:
        return ""
    privileged = context.role is not Role.intern
    lines: list[str] = []
    pending = context.next_pending
    if pending is not None:
        if privileged:
            lines.append(f"Ближайший шаг подопечного — «{pending.title}» (неделя {pending.week}).")
        else:
            lines.append(f"Следующий шаг — «{pending.title}» (неделя {pending.week}).")
    elif privileged:
        lines.append("Подопечный прошёл все шаги чек-листа — можно планировать итоговую встречу.")
    else:
        lines.append("Все пункты чек-листа выполнены — можно переходить к итоговой встрече.")
    if context.reminders:
        reminder_label = (
            "Просроченные напоминания подопечного:" if privileged else "Просроченные напоминания:"
        )
        lines.append(reminder_label)
        lines.extend(f"— {message}" for message in context.reminders)
    return "\n".join(lines)
