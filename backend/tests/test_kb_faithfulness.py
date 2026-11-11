"""Faithfulness smoke: 10 typical intern questions must hit their document.

This is the guardrail for the RAG path — if ingestion, tokenization or the BM25
threshold regress, the first failing case names the question and what came back.
"""

from __future__ import annotations

from app.db import get_session_factory
from app.kb.eval import EVAL_CASES, evaluate


def test_eval_cases_cover_ten_distinct_questions():
    assert len(EVAL_CASES) == 10
    assert len({case.question for case in EVAL_CASES}) == 10
    assert all(case.expected_title for case in EVAL_CASES)


async def test_retriever_answers_every_typical_question():
    async with get_session_factory()() as session:
        results = await evaluate(session)

    failures = [
        {"question": result.case.question, "titles": result.titles}
        for result in results
        if not result.passed
    ]
    assert not failures, failures
    assert all(result.hit for result in results)
