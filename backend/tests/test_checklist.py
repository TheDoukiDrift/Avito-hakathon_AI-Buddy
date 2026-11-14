from __future__ import annotations

from sqlalchemy import select

from app.db import get_session_factory
from app.models import AuditEvent
from tests.conftest import HR_BP, INTERN, MANAGER, MENTOR, auth_headers


async def test_checklist_contains_adr13_structure(client):
    headers = await auth_headers(client, INTERN)
    response = await client.get("/api/checklist", headers=headers)
    assert response.status_code == 200

    body = response.json()
    assert body["total"] == 11
    assert body["done_count"] == 0
    titles = [item["title"] for item in body["items"]]
    assert "Знакомство с командой" in titles
    assert "Запрос инструмента прогресса у куратора" in titles
    assert "Экваторная встреча" in titles
    assert {item["week"] for item in body["items"]} >= {1, 2}
    assert all(item["status"] == "pending" for item in body["items"])


async def test_complete_toggles_and_is_audited(client):
    headers = await auth_headers(client, INTERN)
    body = (await client.get("/api/checklist", headers=headers)).json()
    item_id = body["items"][0]["id"]

    first = await client.post(f"/api/checklist/{item_id}/complete", headers=headers)
    assert first.status_code == 200
    assert first.json()["status"] == "done"

    after = (await client.get("/api/checklist", headers=headers)).json()
    assert after["done_count"] == 1
    completed = next(item for item in after["items"] if item["id"] == item_id)
    assert completed["status"] == "done"

    second = await client.post(f"/api/checklist/{item_id}/complete", headers=headers)
    assert second.json()["status"] == "pending"

    async with get_session_factory()() as session:
        actions = list((await session.execute(select(AuditEvent.action))).scalars())
    assert "checklist.completed" in actions
    assert "checklist.reopened" in actions


async def test_complete_unknown_item_returns_404(client):
    headers = await auth_headers(client, INTERN)
    response = await client.post("/api/checklist/424242/complete", headers=headers)
    assert response.status_code == 404


async def test_sequential_gate_blocks_skipping_ahead(client):
    headers = await auth_headers(client, INTERN)
    body = (await client.get("/api/checklist", headers=headers)).json()
    first, second = body["items"][0], body["items"][1]

    skipped = await client.post(f"/api/checklist/{second['id']}/complete", headers=headers)
    assert skipped.status_code == 409
    assert skipped.json()["detail"] == f"Сначала выполните предыдущий шаг: {first['title']}"

    after = (await client.get("/api/checklist", headers=headers)).json()
    assert after["done_count"] == 0

    first_done = await client.post(f"/api/checklist/{first['id']}/complete", headers=headers)
    assert first_done.status_code == 200

    allowed = await client.post(f"/api/checklist/{second['id']}/complete", headers=headers)
    assert allowed.status_code == 200
    assert allowed.json()["status"] == "done"


async def test_sequential_gate_allows_uncomplete_anywhere(client):
    headers = await auth_headers(client, INTERN)
    body = (await client.get("/api/checklist", headers=headers)).json()
    first, second = body["items"][0], body["items"][1]

    await client.post(f"/api/checklist/{first['id']}/complete", headers=headers)
    await client.post(f"/api/checklist/{second['id']}/complete", headers=headers)

    # Toggling back is always allowed, even though the next item is already done.
    reopened = await client.post(f"/api/checklist/{first['id']}/complete", headers=headers)
    assert reopened.status_code == 200
    assert reopened.json()["status"] == "pending"


async def test_privileged_roles_resolve_the_ward_checklist(client):
    intern_headers = await auth_headers(client, INTERN)
    body = (await client.get("/api/checklist", headers=intern_headers)).json()
    await client.post(f"/api/checklist/{body['items'][0]['id']}/complete", headers=intern_headers)

    # No ?user_id: the backend resolves the target. A mentor/manager gets the intern of
    # their team, HR BP the first intern overall — never their own empty checklist.
    for email in (MENTOR, MANAGER, HR_BP):
        response = await client.get("/api/checklist", headers=await auth_headers(client, email))
        assert response.status_code == 200, email
        payload = response.json()
        assert payload["done_count"] == 1, email
        assert payload["total"] == 11, email


async def test_checklist_requires_auth(client):
    assert (await client.get("/api/checklist")).status_code == 401
