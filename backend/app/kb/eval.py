"""Faithfulness smoke test: 10 typical intern questions → expected document.

For every question the retriever must return at least one chunk, and the best
chunk must come from the document a human would name. The check is lexical and
deterministic on purpose: it is the guardrail that catches a broken tokenizer,
threshold or ingestion before the chat demo does.

Run it from the test suite (`tests/test_kb_faithfulness.py`) or by hand:
`python -m app.kb.eval`.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.db import dispose_engine, get_engine, get_session_factory
from app.kb.ingest import KB_DOCS_DIR, ingest_documents
from app.models import Base
from app.services import kb as kb_service

OTGUL = "Процедура отгула по ТК РФ"
ACCESS = "Доступы Jira и Confluence"
CHECKLIST = "Чек-лист новичка: первые недели"
REVIEW = "Код-стайл и процесс код-ревью"
BRANCHES = "Фича-ветки и окружения"
GRAFANA = "Grafana: дашборды и метрики"
DMS = "ДМС: справочная информация"
TRIPS = "Командировки: как оформить"
TRAINING = "Бюджет на обучение"
CONTACTS = "Контакты HR и наставников"


@dataclass(frozen=True)
class EvalCase:
    question: str
    expected_title: str


EVAL_CASES: tuple[EvalCase, ...] = (
    EvalCase("Как оформить отгул по ТК РФ?", OTGUL),
    EvalCase("Сколько дней отпуска и как согласовать отпуск?", OTGUL),
    EvalCase("Как получить доступ к Jira и Confluence?", ACCESS),
    EvalCase("Что входит в чек-лист новичка в первые недели?", CHECKLIST),
    EvalCase("Как проходит код-ревью и какие правила код-стайла?", REVIEW),
    EvalCase("Как развернуть фича-ветку и какие есть окружения?", BRANCHES),
    EvalCase("Где найти дашборды Grafana и метрики сервиса?", GRAFANA),
    EvalCase("Что делать по ДМС и куда обращаться?", DMS),
    EvalCase("Как оформить командировку?", TRIPS),
    EvalCase("Есть ли бюджет на обучение и как его потратить?", TRAINING),
)


@dataclass(frozen=True)
class EvalResult:
    case: EvalCase
    titles: tuple[str, ...]

    @property
    def passed(self) -> bool:
        """The best chunk comes from the expected document."""
        return bool(self.titles) and self.titles[0] == self.case.expected_title

    @property
    def hit(self) -> bool:
        """The expected document is somewhere in the returned sources."""
        return self.case.expected_title in self.titles


async def evaluate(session: AsyncSession) -> list[EvalResult]:
    """Run every case through the real `search()` path."""
    results: list[EvalResult] = []
    for case in EVAL_CASES:
        sources = await kb_service.search(session, case.question)
        results.append(EvalResult(case=case, titles=tuple(source.title for source in sources)))
    return results


async def main() -> list[EvalResult]:
    async with get_engine().begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with get_session_factory()() as session:
        await ingest_documents(session, KB_DOCS_DIR)
        await session.commit()
        results = await evaluate(session)
    await dispose_engine()
    for result in results:
        mark = "ok  " if result.passed else "FAIL"
        print(f"{mark} {result.case.question} → {list(result.titles)}")
    return results


if __name__ == "__main__":
    outcomes = asyncio.run(main())
    raise SystemExit(0 if all(result.passed for result in outcomes) else 1)
