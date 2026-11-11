from __future__ import annotations

import json

import httpx
import pytest

from app.agent import (
    Agent,
    AgentContext,
    ChatTurn,
    ChecklistSnapshot,
    ContactSnapshot,
    FakeLLM,
    KbSnippet,
    OpenAICompatibleClient,
    build_context,
    build_llm,
)
from app.agent import fake as fake_module
from app.agent.loop import relevant_sources, unique_sources
from app.config import Settings
from app.models import Role
from tests.conftest import INTERN, auth_headers


def _context() -> AgentContext:
    return AgentContext(
        full_name="Доуки Хоши",
        role=Role.intern,
        checklist=[
            ChecklistSnapshot(title="Знакомство с командой", week=1, done=True),
            ChecklistSnapshot(title="Доступы Jira и Confluence", week=1, done=False),
        ],
        contacts=[
            ContactSnapshot(name="Иван", role="наставник", email="mentor@example.com"),
            ContactSnapshot(name="Ольга", role="HR BP", email="hr.bp@example.com"),
        ],
    )


def test_absence_keyword_routes_to_procedure():
    text = fake_module.answer("как оформить отгул завтра?", _context())
    assert "черновик" in text.lower()
    assert "руководител" in text.lower()
    assert "подтверд" in text.lower()


def test_checklist_keyword_summarizes_progress():
    text = fake_module.answer("что у меня по чек-листу?", _context())
    assert "1 из 2" in text
    assert "Доступы Jira и Confluence" in text


def test_routing_keyword_returns_contacts():
    text = fake_module.answer("к кому обратиться по командировкам?", _context())
    assert "Иван" in text
    assert "mentor@example.com" in text


def test_default_answer_points_at_knowledge_base():
    text = fake_module.answer("расскажи про графану", _context())
    assert "базе знаний" in text


def test_rag_sources_win_over_keyword_shortcuts():
    snippet = KbSnippet(
        title="Процедура отгула по ТК РФ",
        source_url="https://example.test/otgul",
        content="Процедура отгула по ТК РФ. Откройте сервис и создайте черновик заявки.",
        score=3.0,
    )
    text = fake_module.answer("как оформить отгул", _context(), [snippet])
    assert "— по материалу «Процедура отгула по ТК РФ»." in text
    assert "черновик" in text


def test_unique_sources_keeps_one_entry_per_document():
    snippets = [
        KbSnippet(title="A", source_url="u", score=2.0),
        KbSnippet(title="A", source_url="u", score=1.5),
        KbSnippet(title="B", source_url="u", score=1.0),
    ]
    assert [snippet.title for snippet in unique_sources(snippets)] == ["A", "B"]


def test_relevant_sources_drops_weak_foreign_documents():
    snippets = [
        KbSnippet(title="A", source_url="u", score=5.0),
        KbSnippet(title="A", source_url="u", score=1.0),
        KbSnippet(title="B", source_url="u", score=1.5),
    ]
    kept = relevant_sources(snippets)
    assert [(snippet.title, snippet.score) for snippet in kept] == [("A", 5.0), ("A", 1.0)]


def test_checklist_answer_without_items():
    context = AgentContext(full_name="Тест", role=Role.intern)
    assert "не назначен" in fake_module.answer("чек-лист", context)


def test_routing_answer_without_contacts():
    context = AgentContext(full_name="Тест", role=Role.intern)
    assert "Контакты" in fake_module.answer("к кому обратиться", context)


def test_checklist_answer_when_all_done():
    context = AgentContext(
        full_name="Тест",
        role=Role.intern,
        checklist=[ChecklistSnapshot(title="Выпускной", week=24, done=True)],
    )
    assert "Все пункты отмечены" in fake_module.answer("чек-лист", context)


async def test_fake_llm_streams_word_chunks():
    llm = FakeLLM()
    chunks = [chunk async for chunk in llm.stream([ChatTurn("user", "отгул")], _context())]
    assert len(chunks) > 5
    assert "отгул" in "".join(chunks).lower() or "черновик" in "".join(chunks).lower()


async def test_agent_emits_tokens_then_done():
    agent = Agent(FakeLLM())
    events = [event async for event in agent.stream("чек-лист", [], _context())]
    assert events[-1].kind == "done"
    assert any(event.kind == "token" for event in events)
    assert "1 из 2" in "".join(event.text for event in events)


def test_build_llm_defaults_to_fake():
    assert isinstance(build_llm(Settings(llm_base_url="", llm_api_key="")), FakeLLM)


def test_build_llm_uses_openai_when_configured():
    settings = Settings(llm_base_url="https://llm.example/v1", llm_api_key="k", llm_model="m")
    client = build_llm(settings)
    assert isinstance(client, OpenAICompatibleClient)
    assert client.model == "m"


def test_openai_payload_carries_role_and_history():
    client = OpenAICompatibleClient(base_url="https://llm.example/v1", api_key="k", model="m")
    payload = client.build_payload(
        [ChatTurn("assistant", "привет"), ChatTurn("user", "как дела")], _context()
    )
    assert payload["model"] == "m"
    assert payload["stream"] is True
    assert payload["messages"][0]["role"] == "system"
    assert "intern" in payload["messages"][0]["content"]
    assert payload["messages"][-1]["content"] == "как дела"


async def test_openai_client_parses_sse_stream():
    body = (
        'data: {"choices":[{"delta":{"content":"При"}}]}\n\n'
        'data: {"choices":[{"delta":{"content":"вет"}}]}\n\n'
        "data: [DONE]\n\n"
    )

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "Bearer k"
        return httpx.Response(200, text=body)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http_client:
        client = OpenAICompatibleClient(
            base_url="https://llm.example/v1", api_key="k", model="m", client=http_client
        )
        chunks = [chunk async for chunk in client.stream([ChatTurn("user", "hi")], _context())]
    assert "".join(chunks) == "Привет"


async def test_openai_client_surfaces_http_errors():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, text="nope")

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http_client:
        client = OpenAICompatibleClient(
            base_url="https://llm.example/v1", api_key="bad", model="m", client=http_client
        )
        with pytest.raises(httpx.HTTPStatusError):
            [chunk async for chunk in client.stream([ChatTurn("user", "hi")], _context())]


async def test_build_context_reads_services(client):
    from app.db import get_session_factory
    from app.services import users as users_service

    headers = await auth_headers(client, INTERN)
    assert headers["Authorization"].startswith("Bearer ")

    async with get_session_factory()() as session:
        intern = await users_service.get_by_email(session, INTERN)
        context = await build_context(session, intern)
    assert context.full_name
    assert len(context.checklist) == 11
    assert len(context.contacts) == 3
    assert context.done_count == 0
    assert context.next_pending is not None


async def test_chat_stream_endpoint_uses_fake_llm(client):
    headers = await auth_headers(client, INTERN)
    async with client.stream(
        "POST", "/api/chat/stream", headers=headers, json={"message": "как оформить отгул?"}
    ) as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        raw = "".join([chunk async for chunk in response.aiter_text()])

    events = [
        json.loads(line[len("data: ") :]) for line in raw.splitlines() if line.startswith("data: ")
    ]
    assert events[-1]["done"] is True
    assert events[-1]["message_id"] is not None
    text = "".join(event.get("token", "") for event in events)
    assert "черновик" in text.lower()
