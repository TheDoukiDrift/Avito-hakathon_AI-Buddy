"""Tool loop on a real (OpenAI-shaped) client: no network, a stub LLM is injected.

The stub emits the same `tool_calls` deltas a provider would; everything after
that — argument validation, the services call, the deterministic answer — is the
production path.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Sequence
from datetime import UTC, date, datetime, timedelta

import httpx

from app.agent import (
    TOOL_SCHEMAS,
    Agent,
    AgentContext,
    ChatTurn,
    FakeLLM,
    KbSnippet,
    LLMEvent,
    OpenAICompatibleClient,
    ToolCall,
    build_context,
    get_llm,
    local_today,
    parse_date_phrase,
)
from app.agent.actions import is_confirmation
from app.agent.base import split_chunks
from app.db import get_session_factory
from app.main import app
from app.models import AbsenceStatus, AbsenceType, Role, User
from app.services import absences as absence_service
from app.services import users as users_service
from tests.conftest import INTERN, auth_headers


class StubToolLLM:
    """A model that streams fixed text and then the tool calls it "decided" on."""

    name = "stub"

    def __init__(
        self,
        *,
        text: str = "",
        tool_calls: Sequence[ToolCall] = (),
    ) -> None:
        self.text = text
        self.tool_calls = list(tool_calls)
        self.calls: list[list[ChatTurn]] = []

    async def stream_turn(
        self,
        messages: Sequence[ChatTurn],
        context: AgentContext,
        tools: Sequence[dict] | None = None,
        sources: Sequence[KbSnippet] = (),
    ) -> AsyncIterator[LLMEvent]:
        self.calls.append(list(messages))
        for chunk in split_chunks(self.text):
            yield LLMEvent(kind="token", text=chunk)
        for call in self.tool_calls:
            yield LLMEvent(kind="tool_call", tool_call=call)


def _create_call(**args: object) -> ToolCall:
    return ToolCall(name="absence_create", arguments=json.dumps(args), call_id="call_1")


async def _intern(session) -> User:
    return await users_service.get_by_email(session, INTERN)


async def _run(agent: Agent, message: str, session, intern: User) -> tuple[str, list]:
    context = await build_context(session, intern)
    events = [
        event async for event in agent.stream(message, [], context, session=session, user=intern)
    ]
    return "".join(event.text for event in events), events


async def test_tool_call_creates_draft_and_asks_for_confirmation():
    async with get_session_factory()() as session:
        intern = await _intern(session)
        # The model tries to act as another user: identity must come from the session.
        call = _create_call(
            user_id=999,
            role="hr_bp",
            type="day_off",
            date_from="2026-12-01",
            date_to="2026-12-01",
            reason="семейные обстоятельства",
        )
        answer, events = await _run(
            Agent(StubToolLLM(tool_calls=[call])), "оформи отгул", session, intern
        )

        draft = await absence_service.latest_own_draft(session, intern)
        assert draft is not None
        assert draft.user_id == intern.id
        assert draft.status is AbsenceStatus.draft
        assert draft.reason == "семейные обстоятельства"

        assert f"Черновик заявки №{draft.id} создан" in answer
        assert "подтверждаю" in answer
        tool_event = next(event for event in events if event.kind == "tool_call")
        assert tool_event.data["request_id"] == draft.id
        assert tool_event.data["tool"] == "absence_create"


async def test_confirmation_sends_latest_draft_to_approval_without_calling_the_llm():
    async with get_session_factory()() as session:
        intern = await _intern(session)
        draft = await absence_service.create_draft(
            session,
            intern,
            absence_type=AbsenceType.day_off,
            date_from=date(2026, 12, 1),
            date_to=date(2026, 12, 1),
            reason="семейные обстоятельства",
        )
        stub = StubToolLLM(text="этот ответ не должен появиться")
        answer, _ = await _run(Agent(stub), "да, подтверждаю", session, intern)

        await session.refresh(draft)
        assert draft.status is AbsenceStatus.pending_approval
        assert f"Заявка №{draft.id} отправлена на согласование руководителю" in answer
        assert stub.calls == []


async def test_missing_date_asks_for_it_and_creates_nothing():
    async with get_session_factory()() as session:
        intern = await _intern(session)
        call = _create_call(type="day_off", reason="семейные обстоятельства")
        answer, _ = await _run(
            Agent(StubToolLLM(tool_calls=[call])), "оформи отгул", session, intern
        )

        assert "дату отсутствия" in answer
        assert "Черновик" in answer
        assert await absence_service.latest_own_draft(session, intern) is None


async def test_invalid_tool_argument_is_reported_honestly():
    async with get_session_factory()() as session:
        intern = await _intern(session)
        call = _create_call(type="party", date_from="2026-12-01", date_to="2026-12-01")
        answer, _ = await _run(
            Agent(StubToolLLM(tool_calls=[call])), "оформи отгул", session, intern
        )

        assert "Не получилось" in answer
        assert "type" in answer
        assert await absence_service.latest_own_draft(session, intern) is None


def test_relative_dates_use_moscow_not_utc():
    # 22:30 UTC on 11 Nov is already 01:30 on 12 Nov in Moscow.
    late_utc = datetime(2026, 11, 11, 22, 30, tzinfo=UTC)
    today = local_today(late_utc)
    assert today == date(2026, 11, 12)
    assert parse_date_phrase("завтра", today=today) == date(2026, 11, 13)
    assert parse_date_phrase("послезавтра", today=today) == date(2026, 11, 14)
    assert parse_date_phrase("сегодня", today=today) == today
    assert parse_date_phrase("2026-12-01", today=today) == date(2026, 12, 1)
    assert parse_date_phrase("когда-нибудь", today=today) is None


async def test_relative_date_in_tool_arguments_resolves_to_local_tomorrow():
    async with get_session_factory()() as session:
        intern = await _intern(session)
        call = _create_call(type="day_off", date_from="завтра", date_to="завтра")
        answer, _ = await _run(
            Agent(StubToolLLM(tool_calls=[call])), "оформи отгул", session, intern
        )

        draft = await absence_service.latest_own_draft(session, intern)
        assert draft is not None
        assert draft.date_from == local_today() + timedelta(days=1)
        assert "подтверждаю" in answer


async def test_openai_client_accumulates_fragmented_tool_call_deltas():
    chunks = [
        {
            "choices": [
                {
                    "delta": {
                        "tool_calls": [
                            {
                                "index": 0,
                                "id": "call_1",
                                "type": "function",
                                "function": {"name": "absence_create", "arguments": ""},
                            }
                        ]
                    }
                }
            ]
        },
        {
            "choices": [
                {
                    "delta": {
                        "tool_calls": [
                            {"index": 0, "function": {"arguments": '{"type": "day_off", '}}
                        ]
                    }
                }
            ]
        },
        {
            "choices": [
                {
                    "delta": {
                        "tool_calls": [
                            {"index": 0, "function": {"arguments": '"date_from": "2026-12-01"}'}}
                        ]
                    }
                }
            ]
        },
    ]
    body = "".join(f"data: {json.dumps(chunk)}\n\n" for chunk in chunks) + "data: [DONE]\n\n"

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=body)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http_client:
        client = OpenAICompatibleClient(
            base_url="https://llm.example/v1", api_key="k", model="m", client=http_client
        )
        events = [
            event
            async for event in client.stream_turn(
                [ChatTurn("user", "оформи отгул")],
                AgentContext(full_name="Т", role=Role.intern),
            )
        ]

    calls = [event.tool_call for event in events if event.kind == "tool_call"]
    assert len(calls) == 1
    assert calls[0] is not None
    assert calls[0].name == "absence_create"
    assert json.loads(calls[0].arguments) == {"type": "day_off", "date_from": "2026-12-01"}


def test_confirmation_requires_a_bare_yes():
    assert is_confirmation("подтверждаю")
    assert is_confirmation("Да, подтверждаю!")
    # A new request inside the same sentence is not a confirmation.
    assert not is_confirmation("подтверждаю, но сначала оформи отпуск")


def test_system_prompt_carries_the_tool_policy():
    client = OpenAICompatibleClient(base_url="https://llm.example/v1", api_key="k", model="m")
    payload = client.build_payload(
        [ChatTurn("user", "привет")],
        AgentContext(full_name="Т", role=Role.intern),
        TOOL_SCHEMAS,
    )
    system = payload["messages"][0]["content"]
    assert "absence_create" in system
    assert "НИКОГДА не создавай заявку без явного подтверждения" in system
    assert "YYYY-MM-DD" in system


async def test_fake_llm_path_uses_local_tomorrow_and_accepts_confirmation():
    async with get_session_factory()() as session:
        intern = await _intern(session)
        await _run(Agent(FakeLLM()), "оформи отгул завтра", session, intern)
        draft = await absence_service.latest_own_draft(session, intern)
        assert draft is not None
        assert draft.date_from == local_today() + timedelta(days=1)

        answer, _ = await _run(Agent(FakeLLM()), "подтверждаю", session, intern)
        await session.refresh(draft)
        assert draft.status is AbsenceStatus.pending_approval
        assert "отправлена на согласование руководителю" in answer


async def test_status_and_list_tools_read_through_the_services_layer():
    async with get_session_factory()() as session:
        intern = await _intern(session)
        draft = await absence_service.create_draft(
            session,
            intern,
            absence_type=AbsenceType.vacation,
            date_from=date(2026, 12, 1),
            date_to=date(2026, 12, 5),
            reason="отпуск",
        )
        stub = StubToolLLM(
            tool_calls=[
                ToolCall(name="absence_list", arguments="{}"),
                ToolCall(name="absence_status", arguments=json.dumps({"request_id": draft.id})),
            ]
        )
        answer, _ = await _run(Agent(stub), "покажи мои заявки", session, intern)

        assert "Заявок: 1" in answer
        assert f"№{draft.id}: отпуск 2026-12-01 — 2026-12-05, статус черновик" in answer


async def test_checklist_complete_tool_marks_the_item():
    from app.services import checklist as checklist_service

    async with get_session_factory()() as session:
        intern = await _intern(session)
        entry = (await checklist_service.get_checklist(session, intern))[0]
        stub = StubToolLLM(
            tool_calls=[
                ToolCall(
                    name="checklist_complete", arguments=json.dumps({"item_id": entry.item.id})
                )
            ]
        )
        answer, _ = await _run(Agent(stub), "отметь первый пункт", session, intern)

        assert f"Пункт «{entry.item.title}» отмечен выполненным" in answer
        refreshed = (await checklist_service.get_checklist(session, intern))[0]
        assert refreshed.status.value == "done"


async def test_unknown_tool_and_broken_arguments_are_reported_not_raised():
    async with get_session_factory()() as session:
        intern = await _intern(session)
        stub = StubToolLLM(
            tool_calls=[
                ToolCall(name="drop_database", arguments="{}"),
                ToolCall(name="absence_create", arguments="{not json"),
            ]
        )
        answer, _ = await _run(Agent(stub), "сделай что-нибудь", session, intern)

        assert "неизвестный инструмент drop_database" in answer
        assert "не удалось разобрать аргументы" in answer
        assert await absence_service.latest_own_draft(session, intern) is None


async def test_chat_endpoint_runs_injected_llm_tool_call(client):
    """The router takes its client from a dependency, so a stub replaces the network."""
    stub = StubToolLLM(
        tool_calls=[_create_call(type="day_off", date_from="2026-12-01", date_to="2026-12-01")]
    )
    app.dependency_overrides[get_llm] = lambda: stub
    try:
        headers = await auth_headers(client, INTERN)
        async with client.stream(
            "POST", "/api/chat/stream", headers=headers, json={"message": "оформи отгул"}
        ) as response:
            assert response.status_code == 200
            raw = "".join([chunk async for chunk in response.aiter_text()])
        events = [
            json.loads(line[len("data: ") :])
            for line in raw.splitlines()
            if line.startswith("data: ")
        ]
        answer = "".join(event.get("token", "") for event in events)
        assert "подтверждаю" in answer

        history = (await client.get("/api/chat/history", headers=headers)).json()
        assert history[-1]["role"] == "assistant"
        assert history[-1]["tool_calls"][0]["tool"] == "absence_create"
    finally:
        app.dependency_overrides.pop(get_llm, None)
