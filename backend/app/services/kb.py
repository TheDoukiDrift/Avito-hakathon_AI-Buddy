"""Knowledge-base retrieval for the RAG scenario.

Documents are ingested from `backend/kb_docs/*.md` into `kb_documents`, split into
`kb_chunks` (see `app.kb.ingest`) and ranked with BM25 (see `app.kb.retrieval`).
No embeddings and no vector store: the prototype must run offline, and BM25 is
the honest fallback PLAN §5 names. Swapping in pgvector later means replacing
`search()` only.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.kb.retrieval import rank_chunks
from app.models import KbChunk, KbDocument


@dataclass(frozen=True)
class Source:
    """A retrieved chunk as the agent and the UI see it."""

    title: str
    source_url: str
    content: str
    doc_id: int
    chunk_index: int
    score: float = 0.0

    def as_source(self) -> dict[str, str]:
        return {"title": self.title, "source_url": self.source_url}


async def all_chunks(session: AsyncSession) -> list[Source]:
    """Every chunk with its document's source URL — the BM25 corpus."""
    statement = (
        select(KbChunk, KbDocument.source_url)
        .join(KbDocument, KbDocument.id == KbChunk.doc_id)
        .order_by(KbChunk.id)
    )
    rows = (await session.execute(statement)).all()
    return [
        Source(
            title=chunk.title,
            source_url=source_url,
            content=chunk.content,
            doc_id=chunk.doc_id,
            chunk_index=chunk.chunk_index,
        )
        for chunk, source_url in rows
    ]


async def search(session: AsyncSession, query: str, limit: int = 3) -> list[Source]:
    """Top-`limit` chunks over the relevance threshold (empty list = nothing matched)."""
    ranked = rank_chunks(query, await all_chunks(session), limit=limit)
    return [replace(source, score=score) for source, score in ranked]
