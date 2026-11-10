from __future__ import annotations

from sqlalchemy import select

from app.db import get_session_factory
from app.models import AuditEvent
from tests.conftest import INTERN, auth_headers


async def test_history_starts_empty(client):
    headers = await auth_headers(client, INTERN)
    response = await client.get("/api/chat/history", headers=headers)
    assert response.status_code == 200
    assert response.json() == []


async def test_chat_persists_question_and_answer(client):
    headers = await auth_headers(client, INTERN)
    async with client.stream(
        "POST", "/api/chat/stream", headers=headers, json={"message": "что у меня по чек-листу?"}
    ) as response:
        assert response.status_code == 200
        _ = [chunk async for chunk in response.aiter_text()]

    history = (await client.get("/api/chat/history", headers=headers)).json()
    assert [message["role"] for message in history] == ["user", "assistant"]
    assert history[0]["content"] == "что у меня по чек-листу?"
    assert "чек-лист" in history[1]["content"].lower()

    async with get_session_factory()() as session:
        actions = list((await session.execute(select(AuditEvent.action))).scalars())
    assert "chat.message" in actions
    assert "chat.answer" in actions


async def test_chat_rejects_empty_message(client):
    headers = await auth_headers(client, INTERN)
    response = await client.post("/api/chat/stream", headers=headers, json={"message": ""})
    assert response.status_code == 422


async def test_chat_requires_auth(client):
    response = await client.post("/api/chat/stream", json={"message": "привет"})
    assert response.status_code == 401
