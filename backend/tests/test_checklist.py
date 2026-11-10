from __future__ import annotations

from sqlalchemy import select

from app.db import get_session_factory
from app.models import AuditEvent
from tests.conftest import INTERN, auth_headers


async def test_checklist_contains_adr13_structure(client):
    headers = await auth_headers(client, INTERN)
    response = await client.get("/api/checklist", headers=headers)
    assert response.status_code == 200

    body = response.json()
    assert body["total"] == 11
    assert body["done"] == 0
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
    assert after["done"] == 1
    completed = next(item for item in after["items"] if item["id"] == item_id)
    assert completed["completed_at"] is not None

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


async def test_checklist_requires_auth(client):
    assert (await client.get("/api/checklist")).status_code == 401
