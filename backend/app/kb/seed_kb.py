"""`python -m app.kb.seed_kb` — (re)ingest `backend/kb_docs/` into the database.

Idempotent: documents are upserted by title, chunks are rebuilt only when the
markdown changed. `app.seeds` calls the same `ingest_documents()`, so container
start-up and this command always agree.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from app.db import dispose_engine, get_engine, get_session_factory
from app.kb.ingest import KB_DOCS_DIR, ingest_documents
from app.models import Base


async def main(docs_dir: Path | None = None) -> dict[str, int]:
    async with get_engine().begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with get_session_factory()() as session:
        report = await ingest_documents(session, docs_dir or KB_DOCS_DIR)
        await session.commit()
    await dispose_engine()
    return report.as_dict()


if __name__ == "__main__":
    print(asyncio.run(main()))
