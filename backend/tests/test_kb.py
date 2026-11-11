"""Knowledge-base ingestion + lexical retrieval units (no LLM involved)."""

from __future__ import annotations

from types import SimpleNamespace

from app.db import get_session_factory
from app.kb.ingest import chunk_document, ingest_documents, load_documents
from app.kb.retrieval import rank_chunks, stem, tokenize
from app.services import kb


def _all_chunks() -> list[SimpleNamespace]:
    chunks: list[SimpleNamespace] = []
    for document in load_documents():
        for index, content in enumerate(chunk_document(document.title, document.content)):
            chunks.append(SimpleNamespace(content=content, title=document.title, index=index))
    return chunks


def test_kb_docs_folder_holds_ten_documents():
    documents = load_documents()
    assert len(documents) == 10
    assert all(document.title and document.source_url for document in documents)
    assert any("consultant.ru" in document.source_url for document in documents)


def test_chunking_prefixes_title_and_stays_in_range():
    document = next(item for item in load_documents() if item.title == "Процедура отгула по ТК РФ")
    chunks = chunk_document(document.title, document.content)
    assert len(chunks) >= 2
    for chunk in chunks:
        assert chunk.startswith(document.title)
        assert 200 <= len(chunk) <= 600


def test_chunking_splits_oversized_paragraphs():
    chunks = chunk_document("Документ", "А" * 1500)
    assert len(chunks) > 1
    assert all(len(chunk) <= 600 for chunk in chunks)


def test_stemming_meets_russian_inflections():
    assert stem("отгула") == stem("отгул") == "отгул"
    assert stem("доступы") == stem("доступ") == "доступ"
    assert stem("графане") == stem("графана")


def test_tokenize_drops_stop_words_and_short_words():
    assert tokenize("как оформить отгул") == ["оформит", "отгул"]


def test_rank_returns_the_relevant_document_first():
    ranked = rank_chunks("как оформить отгул", _all_chunks())
    assert ranked
    assert ranked[0][0].title == "Процедура отгула по ТК РФ"
    assert ranked[0][1] > 0


def test_rank_returns_nothing_without_term_overlap():
    assert rank_chunks("как приготовить борщ", _all_chunks()) == []


async def test_ingest_is_idempotent():
    async with get_session_factory()() as session:
        first = await ingest_documents(session)
        await session.commit()
        second = await ingest_documents(session)
        await session.commit()

    assert first.documents == second.documents == 10
    assert first.chunks == second.chunks
    assert second.created == 0
    assert second.updated == 0


async def test_search_returns_sources_with_urls_and_text():
    async with get_session_factory()() as session:
        sources = await kb.search(session, "как оформить отгул?")
    assert sources
    assert sources[0].title == "Процедура отгула по ТК РФ"
    assert sources[0].source_url.startswith("https://")
    assert sources[0].content
    assert sources[0].score > 0


async def test_search_returns_nothing_for_an_unrelated_question():
    async with get_session_factory()() as session:
        assert await kb.search(session, "как приготовить борщ?") == []
