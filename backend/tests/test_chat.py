from __future__ import annotations

import json

from sqlalchemy import select

from app.db import get_session_factory
from app.models import AuditEvent
from tests.conftest import INTERN, auth_headers


async def _stream_answer(client, headers: dict[str, str], message: str) -> tuple[str, dict]:
    """Run one SSE turn and return (answer text, final `done` event payload)."""
    async with client.stream(
        "POST", "/api/chat/stream", headers=headers, json={"message": message}
    ) as response:
        assert response.status_code == 200
        raw = "".join([chunk async for chunk in response.aiter_text()])
    events = [
        json.loads(line[len("data: ") :]) for line in raw.splitlines() if line.startswith("data: ")
    ]
    answer = "".join(event.get("token", "") for event in events)
    done = next(event for event in events if event.get("done"))
    return answer, done


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


async def test_s1_answer_cites_the_retrieved_document(client):
    headers = await auth_headers(client, INTERN)
    answer, done = await _stream_answer(client, headers, "как оформить отгул?")

    assert "— по материалу «Процедура отгула по ТК РФ»." in answer
    assert done["sources"][0]["title"] == "Процедура отгула по ТК РФ"
    assert done["sources"][0]["source_url"].startswith("https://www.consultant.ru/")


async def test_s1_follow_up_keeps_conversation_context(client):
    headers = await auth_headers(client, INTERN)
    await _stream_answer(client, headers, "как оформить отгул?")
    answer, done = await _stream_answer(client, headers, "а какие сроки согласования?")

    # The follow-up carries no topic of its own: history supplies it, so the
    # answer still cites the absence procedure instead of the fallback note.
    assert "— по материалу «Процедура отгула по ТК РФ»." in answer
    assert done["sources"][0]["title"] == "Процедура отгула по ТК РФ"

    history = (await client.get("/api/chat/history", headers=headers)).json()
    assert [message["role"] for message in history] == [
        "user",
        "assistant",
        "user",
        "assistant",
    ]
    assert history[2]["content"] == "а какие сроки согласования?"


async def test_s1_unrelated_question_falls_back_without_citations(client):
    headers = await auth_headers(client, INTERN)
    answer, done = await _stream_answer(client, headers, "как приготовить борщ?")

    assert "базе знаний" in answer
    assert "по материалу" not in answer
    assert done["sources"] == []
