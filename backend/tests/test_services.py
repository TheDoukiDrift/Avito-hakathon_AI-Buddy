from __future__ import annotations

import pytest

from app.db import get_session_factory
from app.errors import NotFoundError
from app.models import Role, User
from app.services import audit, checklist, contacts, rbac, users
from tests.conftest import HR_BP, INTERN, MENTOR


def _user(uid: int, role: Role, team: str | None = "Platform") -> User:
    return User(id=uid, email=f"u{uid}@example.com", role=role, full_name=f"U{uid}", team=team)


def test_rbac_matrix_checklist():
    intern = _user(1, Role.intern)
    mentor = _user(2, Role.mentor)
    manager = _user(3, Role.manager)
    hr = _user(4, Role.hr_bp)
    other_team_mentor = _user(5, Role.mentor, team="Other")

    assert rbac.can_view_checklist(intern, intern)
    assert rbac.can_view_checklist(mentor, intern)
    assert rbac.can_view_checklist(manager, intern)
    assert rbac.can_view_checklist(hr, intern)
    # "–" cells
    assert not rbac.can_view_checklist(intern, mentor)
    assert not rbac.can_view_checklist(mentor, manager)
    assert not rbac.can_view_checklist(other_team_mentor, intern)
    assert not rbac.can_view_checklist(intern, hr)

    assert rbac.can_complete_checklist(intern, intern)
    assert not rbac.can_complete_checklist(mentor, intern)
    assert not rbac.can_complete_checklist(hr, intern)


def test_rbac_matrix_absences():
    intern = _user(1, Role.intern)
    mentor = _user(2, Role.mentor)
    hr = _user(4, Role.hr_bp)

    assert rbac.can_view_absence(intern, intern)
    assert rbac.can_view_absence(mentor, intern)
    assert rbac.can_view_absence(hr, mentor)
    assert not rbac.can_view_absence(intern, mentor)

    assert rbac.can_approve_absence(mentor, intern)
    assert rbac.can_approve_absence(hr, intern)
    assert not rbac.can_approve_absence(intern, intern)  # no self-approval
    assert not rbac.can_approve_absence(mentor, mentor)
    assert not rbac.can_approve_absence(hr, hr)


def test_rbac_audit_and_contacts():
    # Every role has an audit feed; the *scope* narrows it (README matrix).
    assert rbac.can_view_audit(_user(1, Role.intern))
    assert rbac.can_view_audit(_user(2, Role.mentor))
    assert rbac.audit_scope(_user(1, Role.intern)) == "own"
    assert rbac.audit_scope(_user(2, Role.mentor)) == "team"
    assert rbac.audit_scope(_user(3, Role.manager)) == "team"
    assert rbac.audit_scope(_user(4, Role.hr_bp)) == "all"
    assert rbac.can_view_contacts(_user(1, Role.intern))


async def test_first_intern_returns_self_for_intern():
    async with get_session_factory()() as session:
        intern = await users.get_by_email(session, INTERN)
        assert await users.first_intern(session, intern) is intern


async def test_first_intern_returns_team_intern_for_privileged():
    async with get_session_factory()() as session:
        mentor = await users.get_by_email(session, MENTOR)
        target = await users.first_intern(session, mentor)
        assert target.email == INTERN


async def test_first_intern_raises_when_team_is_empty():
    async with get_session_factory()() as session:
        loner = User(
            email="loner@example.com",
            password_hash="x",
            role=Role.mentor,
            full_name="Один",
            team="Empty",
        )
        session.add(loner)
        await session.flush()
        with pytest.raises(NotFoundError):
            await users.first_intern(session, loner)


async def test_summarize_counts_done_and_next():
    async with get_session_factory()() as session:
        intern = await users.get_by_email(session, INTERN)
        entries = await checklist.get_checklist(session, intern)
        done, total, next_entry = checklist.summarize(entries)
        assert (done, total) == (0, 11)
        assert next_entry is not None


async def test_contacts_filtered_by_team_and_query():
    async with get_session_factory()() as session:
        intern = await users.get_by_email(session, INTERN)
        everyone = await contacts.list_contacts(session, intern)
        assert len(everyone) == 3
        hr_only = await contacts.list_contacts(session, intern, "HR")
        assert [contact.email for contact in hr_only] == ["hr.bp@example.com"]


async def test_audit_events_are_listed_newest_first():
    async with get_session_factory()() as session:
        hr = await users.get_by_email(session, HR_BP)
        await audit.log(session, hr.id, "test.first")
        await audit.log(session, hr.id, "test.second")
        await session.commit()
        events = await audit.list_events(session, limit=2)
        assert [event.action for event in events] == ["test.second", "test.first"]
