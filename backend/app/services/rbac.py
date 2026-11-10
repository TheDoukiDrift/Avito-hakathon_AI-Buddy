"""Access control matrix (ADR-08).

RBAC gives the role its class of access, ABAC narrows it by relation
("свои" / "подопечные" / "команда" / "все"). Every rule here has a negative
test in `tests/test_rbac.py`.
"""

from __future__ import annotations

from typing import Literal

from app.models import Role, User

PRIVILEGED_ROLES = (Role.mentor, Role.manager, Role.hr_bp)


def is_privileged(actor: User) -> bool:
    return actor.role in PRIVILEGED_ROLES


def same_team(actor: User, target: User) -> bool:
    return bool(actor.team) and actor.team == target.team


def _is_ward(actor: User, target: User) -> bool:
    """A mentor/manager may only touch interns of their own team."""
    return target.role is Role.intern and same_team(actor, target)


def can_view_checklist(actor: User, target: User) -> bool:
    if actor.id == target.id:
        return True
    if actor.role is Role.hr_bp:
        return True
    return actor.role in (Role.mentor, Role.manager) and _is_ward(actor, target)


def can_complete_checklist(actor: User, target: User) -> bool:
    # The matrix only grants completion of one's own checklist, and only to an intern:
    # mentors/managers/HR BP see wards read-only.
    return actor.id == target.id and actor.role is Role.intern


def can_view_absence(actor: User, target: User) -> bool:
    if actor.id == target.id:
        return True
    if actor.role is Role.hr_bp:
        return True
    return actor.role in (Role.mentor, Role.manager) and _is_ward(actor, target)


def can_approve_absence(actor: User, target: User) -> bool:
    # Nobody approves their own request (no self-approval, even for HR BP).
    if actor.id == target.id:
        return False
    if actor.role is Role.hr_bp:
        return True
    return actor.role in (Role.mentor, Role.manager) and _is_ward(actor, target)


def can_view_contacts(actor: User) -> bool:
    return True


def can_view_audit(actor: User) -> bool:
    # Every role has an audit feed; the *scope* is narrowed by `audit_scope`.
    return True


def audit_scope(actor: User) -> Literal["all", "team", "own"]:
    """Which slice of `audit_events` a role may read (README matrix)."""
    if actor.role is Role.hr_bp:
        return "all"
    if actor.role in (Role.mentor, Role.manager):
        return "team"
    return "own"
