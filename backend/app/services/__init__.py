"""Domain services shared by the REST routers and the MCP server.

Thin imitations on purpose (ADR-02): the value of the prototype is in the
scenarios, not in re-implementing corporate systems.
"""

from app.services import (
    absences,
    audit,
    chat,
    checklist,
    contacts,
    kb,
    rbac,
    reminders,
    users,
)

__all__ = [
    "absences",
    "audit",
    "chat",
    "checklist",
    "contacts",
    "kb",
    "rbac",
    "reminders",
    "users",
]
