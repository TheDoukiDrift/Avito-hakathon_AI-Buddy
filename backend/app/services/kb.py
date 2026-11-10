"""Knowledge base retrieval for the RAG scenario.

Honest, deliberately small: no embeddings, no vector store. Documents are seeded
synthetically and ranked by keyword overlap — enough for the prototype to show a
real retrieve-then-answer path and to return `sources` the UI can display.
Swapping in pgvector later means replacing `search()` only.
"""

from __future__ import annotations

import re

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import KbDocument

# Russian is heavily inflected ("отгул"/"отгула"/"отгуле"), so compare stems:
# keep the first N characters of a word instead of shipping a stemmer.
_STEM_LENGTH = 5
_MIN_WORD_LENGTH = 4
_WORD_RE = re.compile(r"[\w-]+", re.UNICODE)


def _stem(word: str) -> str:
    return word.lower()[:_STEM_LENGTH]


def query_terms(query: str) -> set[str]:
    """Significant word stems of a question, minus common Russian stop words."""
    terms = set()
    for word in _WORD_RE.findall(query.lower()):
        if len(word) < _MIN_WORD_LENGTH or word in STOP_WORDS:
            continue
        terms.add(_stem(word))
    return terms


STOP_WORDS = frozenset(
    {
        "как",
        "что",
        "где",
        "когда",
        "кто",
        "чем",
        "мне",
        "меня",
        "можно",
        "нужно",
        "надо",
        "это",
        "для",
        "про",
        "или",
        "если",
        "чтобы",
        "такое",
        "расскажи",
        "подскажи",
    }
)


def _document_terms(document: KbDocument) -> set[str]:
    haystack = " ".join((document.title, document.keywords, document.content))
    return {_stem(word) for word in _WORD_RE.findall(haystack.lower()) if len(word) >= 3}


def rank_documents(query: str, documents: list[KbDocument], limit: int = 3) -> list[KbDocument]:
    """Pure ranking: documents sharing the most stems with the question win."""
    terms = query_terms(query)
    if not terms:
        return []
    scored: list[tuple[int, KbDocument]] = []
    for document in documents:
        score = len(terms & _document_terms(document))
        if score:
            scored.append((score, document))
    scored.sort(key=lambda pair: (-pair[0], pair[1].id))
    return [document for _, document in scored[:limit]]


async def all_documents(session: AsyncSession) -> list[KbDocument]:
    return list((await session.execute(select(KbDocument).order_by(KbDocument.id))).scalars())


async def search(session: AsyncSession, query: str, limit: int = 3) -> list[KbDocument]:
    """Keyword retrieval over `kb_documents` (empty list = nothing matched)."""
    return rank_documents(query, await all_documents(session), limit)
