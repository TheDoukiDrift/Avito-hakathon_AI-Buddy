"""MCP tools are a second front door to the same services — test them directly."""

from __future__ import annotations

import pytest

from app.errors import ForbiddenError, ValidationError
from app.models import Role
from mcp_server import tools
from mcp_server.server import SERVER_NAME, build_server
from tests.conftest import HR_BP, INTERN, MENTOR, user_id


async def test_server_registers_every_tool():
    server = build_server()
    assert server.name == SERVER_NAME
    registered = {tool.name for tool in await server.list_tools()}
    assert registered == {
        "absence_create",
        "absence_status",
        "absence_list",
        "checklist_get",
        "checklist_complete",
        "contacts_lookup",
    }


async def test_checklist_get_returns_progress(client):
    intern_id = await user_id(client, INTERN)
    payload = await tools.checklist_get(intern_id, Role.intern.value)
    assert payload["total"] == 11
    assert payload["done"] == 0
    assert payload["next"] == "Знакомство с командой"


async def test_checklist_complete_toggles(client):
    intern_id = await user_id(client, INTERN)
    checklist = await tools.checklist_get(intern_id, Role.intern.value)
    item_id = checklist["items"][0]["id"]

    done = await tools.checklist_complete(intern_id, Role.intern.value, item_id)
    assert done["status"] == "done"
    again = await tools.checklist_complete(intern_id, Role.intern.value, item_id)
    assert again["status"] == "pending"


async def test_checklist_get_enforces_rbac(client):
    intern_id = await user_id(client, INTERN)
    mentor_id = await user_id(client, MENTOR)

    # the intern cannot look at the mentor's checklist
    with pytest.raises(ForbiddenError):
        await tools.checklist_get(intern_id, Role.intern.value, target_user_id=mentor_id)


async def test_checklist_get_rejects_role_mismatch(client):
    intern_id = await user_id(client, INTERN)
    with pytest.raises(ForbiddenError):
        await tools.checklist_get(intern_id, Role.hr_bp.value)


async def test_absence_lifecycle_via_tools(client):
    intern_id = await user_id(client, INTERN)
    draft = await tools.absence_create(
        intern_id, Role.intern.value, "day_off", "2026-12-01", "2026-12-01", "Личные дела"
    )
    assert draft["status"] == "draft"

    status = await tools.absence_status(intern_id, Role.intern.value, draft["id"])
    assert status["id"] == draft["id"]

    listed = await tools.absence_list(intern_id, Role.intern.value)
    assert listed["count"] == 1


async def test_absence_tools_validate_input(client):
    intern_id = await user_id(client, INTERN)
    with pytest.raises(ValidationError):
        await tools.absence_create(
            intern_id, Role.intern.value, "sabbatical", "2026-12-01", "2026-12-01"
        )
    with pytest.raises(ValidationError):
        await tools.absence_create(
            intern_id, Role.intern.value, "day_off", "01.12.2026", "2026-12-01"
        )


async def test_absence_status_enforces_ownership(client):
    intern_id = await user_id(client, INTERN)
    hr_id = await user_id(client, HR_BP)
    draft = await tools.absence_create(
        hr_id, Role.hr_bp.value, "vacation", "2026-12-10", "2026-12-12"
    )
    with pytest.raises(ForbiddenError):
        await tools.absence_status(intern_id, Role.intern.value, draft["id"])


async def test_contacts_lookup(client):
    intern_id = await user_id(client, INTERN)
    payload = await tools.contacts_lookup(intern_id, Role.intern.value, "наставник")
    assert payload["count"] == 1
    assert payload["items"][0]["email"] == "mentor@example.com"
