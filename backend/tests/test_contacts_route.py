"""S4: «к кому обратиться» — routing out of the knowledge base and to a human."""

from __future__ import annotations

from sqlalchemy import select

from app.db import get_session_factory
from app.models import Contact, Role, User
from app.services import contacts as contacts_service
from mcp_server import tools
from tests.conftest import INTERN, user_id


async def _route(question: str) -> Contact | None:
    async with get_session_factory()() as session:
        intern_id = (
            await session.execute(
                select(User.id).where(User.role == Role.intern).order_by(User.id).limit(1)
            )
        ).scalar_one()
        return await contacts_service.route_question(session, intern_id, question)


async def test_kb_hit_has_no_contact():
    # The absence procedure is in the knowledge base: the buddy answers itself.
    contact = await _route("как оформить отгул?")
    assert contact is None


async def test_out_of_kb_question_routes_to_mentor():
    contact = await _route("как приготовить борщ?")
    assert contact is not None
    assert contact.role == "наставник"
    assert contact.email == "mentor@example.com"


async def test_salary_question_escalates_to_first_in_chain():
    # «зарплат» is an escalation marker: even though retrieval is irrelevant here,
    # the chain decides — наставник is first, then руководитель, then HR BP.
    contact = await _route("у меня вопрос про зарплату")
    assert contact is not None
    assert contact.role == "наставник"


async def test_escalation_marker_wins_over_a_kb_hit():
    # The KB does have the absence procedure, but «не получается» asks for a person.
    contact = await _route("не получается оформить отгул")
    assert contact is not None
    assert contact.role == "наставник"


async def test_escalation_chain_order_and_markers():
    mentor = Contact(name="М", role="наставник", email="m@example.com")
    manager = Contact(name="Р", role="руководитель", email="r@example.com")
    hr = Contact(name="H", role="HR BP", email="h@example.com")
    chain = contacts_service.escalation_chain([hr, manager, mentor])
    assert [contact.role for contact in chain] == ["наставник", "руководитель", "HR BP"]

    assert contacts_service.has_escalation_markers("у меня конфликт с коллегой")
    assert contacts_service.has_escalation_markers("не могу разобраться")
    assert not contacts_service.has_escalation_markers("как оформить отгул")


async def test_mcp_contacts_route_tool(client):
    intern = await user_id(client, INTERN)
    hit = await tools.contacts_route(intern, "как оформить отгул?")
    assert hit == {"contact": None, "escalation": False}

    miss = await tools.contacts_route(intern, "где взять кофе?")
    assert miss["contact"] is not None
    assert miss["contact"]["email"] == "mentor@example.com"

    escalated = await tools.contacts_route(intern, "не получается оформить отгул")
    assert escalated["escalation"] is True
    assert escalated["contact"]["role"] == "наставник"


async def test_mcp_registers_contacts_route():
    from mcp_server.server import build_server

    registered = {tool.name for tool in await build_server().list_tools()}
    assert "contacts_route" in registered
    assert len(registered) == 7


async def test_unrelated_question_falls_back_to_mentor_in_chat(client):
    import json

    from tests.conftest import auth_headers

    headers = await auth_headers(client, INTERN)
    async with client.stream(
        "POST", "/api/chat/stream", headers=headers, json={"message": "как приготовить борщ?"}
    ) as response:
        raw = "".join([chunk async for chunk in response.aiter_text()])
    events = [
        json.loads(line[len("data: ") :]) for line in raw.splitlines() if line.startswith("data: ")
    ]
    answer = "".join(event.get("token", "") for event in events)
    assert "Не нашёл в базе знаний" in answer
    assert "mentor@example.com" in answer


async def test_routing_question_names_the_chain_in_chat(client):
    """README S4: «кто занимается командировками?» must name people, not an empty team."""
    import json

    from tests.conftest import auth_headers

    headers = await auth_headers(client, INTERN)
    async with client.stream(
        "POST",
        "/api/chat/stream",
        headers=headers,
        json={"message": "кто занимается командировками?"},
    ) as response:
        raw = "".join([chunk async for chunk in response.aiter_text()])
    events = [
        json.loads(line[len("data: ") :]) for line in raw.splitlines() if line.startswith("data: ")
    ]
    answer = "".join(event.get("token", "") for event in events)
    assert "не заполнены" not in answer
    assert "mentor@example.com" in answer
