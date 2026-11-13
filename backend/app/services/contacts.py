"""Team contacts — the routing source for S4 «к кому обратиться».

`route_question` is the deterministic half of S4: the buddy answers from the
knowledge base when it can, and otherwise (or when the question carries an
escalation marker) names the first person of the escalation chain
наставник → руководитель → HR BP (Q&A 00:36:19). Both LLM paths use it, so the
routing does not depend on the model's mood.
"""

from __future__ import annotations

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import ForbiddenError
from app.models import Contact, User
from app.services import kb as kb_service
from app.services import rbac
from app.services import users as users_service

# Markers that must not be answered with a document even when the KB has one:
# a person is waiting on the other end of these.
ESCALATION_MARKERS = (
    "не могу",
    "не получается",
    "жалоб",
    "конфликт",
    "зарплат",
    "личн",
)

# Order of the chain from the Q&A (00:36:19). Matched as substrings of `contacts.role`.
_ESCALATION_ROLES = ("наставник", "руководител", "hr")


def has_escalation_markers(question: str) -> bool:
    text = question.lower()
    return any(marker in text for marker in ESCALATION_MARKERS)


def _role_rank(role: str) -> int:
    lowered = role.lower()
    for index, needle in enumerate(_ESCALATION_ROLES):
        if needle in lowered:
            return index
    return len(_ESCALATION_ROLES)


def escalation_chain(contacts: list[Contact]) -> list[Contact]:
    """Contacts in chain order: наставник → руководитель → HR BP."""
    return sorted(contacts, key=lambda contact: (_role_rank(contact.role), contact.id))


async def _chain_for(session: AsyncSession, user: User) -> list[Contact]:
    stmt = select(Contact)
    if user.team:
        stmt = stmt.where(or_(Contact.team == user.team, Contact.team.is_(None)))
    rows = list((await session.execute(stmt)).scalars())
    if not rows:
        rows = list((await session.execute(select(Contact))).scalars())
    return escalation_chain(rows)


async def route_question(session: AsyncSession, user_id: int, question: str) -> Contact | None:
    """The next person to ask, or `None` when the knowledge base already answers.

    A question with an escalation marker is routed even if retrieval finds a
    document — «не получается войти в Jira» wants a human, not an article.
    """
    user = await users_service.get_user(session, user_id)
    if not has_escalation_markers(question) and await kb_service.search(session, question):
        return None
    chain = await _chain_for(session, user)
    return chain[0] if chain else None


async def list_contacts(
    session: AsyncSession, actor: User, query: str | None = None
) -> list[Contact]:
    if not rbac.can_view_contacts(actor):
        raise ForbiddenError("Контакты недоступны вашей роли")

    stmt = select(Contact)
    if actor.team:
        stmt = stmt.where(Contact.team == actor.team)
    if query:
        needle = f"%{query.strip().lower()}%"
        stmt = stmt.where(
            or_(
                Contact.name.ilike(needle),
                Contact.role.ilike(needle),
                Contact.email.ilike(needle),
            )
        )
    stmt = stmt.order_by(Contact.id)
    return list((await session.execute(stmt)).scalars())
