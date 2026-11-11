"""Markdown knowledge-base ingestion: `kb_docs/*.md` → `kb_documents` + `kb_chunks`.

A document is plain markdown with a tiny frontmatter block:

    ---
    title: Процедура отгула по ТК РФ
    source_url: https://www.consultant.ru/document/cons_doc_LAW_34683/
    keywords: отгул отпуск заявка
    ---

Chunking is deliberately simple and dependency-free: split by headings, pack
paragraphs into 300–600 character chunks (plus the document-title prefix) so a
retrieved fragment is self-describing even out of context. Ingestion is
idempotent: documents are upserted by title and their chunks are rebuilt only
when the markdown changed.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import KbChunk, KbDocument

KB_DOCS_DIR = Path(__file__).resolve().parents[2] / "kb_docs"

MIN_CHUNK_CHARS = 300
MAX_CHUNK_CHARS = 600

_FRONTMATTER_RE = re.compile(r"\A---[ \t]*\n(.*?)\n---[ \t]*\n?", re.DOTALL)
_HEADING_RE = re.compile(r"^#{1,6}\s+(.+?)\s*$")
_FIRST_HEADING_RE = re.compile(r"^#{1,6}\s+(.+?)\s*$", re.MULTILINE)


@dataclass(frozen=True)
class ParsedDocument:
    """A markdown document after frontmatter parsing."""

    title: str
    source_url: str
    content: str
    keywords: str = ""


@dataclass
class IngestReport:
    """What one ingestion run did — printed by `python -m app.kb.seed_kb`."""

    documents: int = 0
    created: int = 0
    updated: int = 0
    chunks: int = 0

    def as_dict(self) -> dict[str, int]:
        return {
            "documents": self.documents,
            "created": self.created,
            "updated": self.updated,
            "chunks": self.chunks,
        }


def _parse_frontmatter(raw: str) -> tuple[dict[str, str], str]:
    match = _FRONTMATTER_RE.match(raw)
    if match is None:
        return {}, raw
    meta: dict[str, str] = {}
    for line in match.group(1).splitlines():
        key, separator, value = line.partition(":")
        if separator:
            meta[key.strip().lower()] = value.strip()
    return meta, raw[match.end() :]


def _first_heading(body: str) -> str | None:
    match = _FIRST_HEADING_RE.search(body)
    return match.group(1).strip() if match else None


def _split_sections(body: str) -> list[tuple[str | None, str]]:
    """Split markdown into `(heading, text)` pairs; text before the first heading has None."""
    sections: list[tuple[str | None, str]] = []
    heading: str | None = None
    lines: list[str] = []
    for line in body.splitlines():
        match = _HEADING_RE.match(line)
        if match:
            if any(part.strip() for part in lines):
                sections.append((heading, "\n".join(lines)))
            heading = match.group(1).strip()
            lines = []
        else:
            lines.append(line)
    if any(part.strip() for part in lines):
        sections.append((heading, "\n".join(lines)))
    return sections


def _split_long(text: str, max_chars: int) -> list[str]:
    """Break a single oversized paragraph at sentence boundaries, then hard-split."""
    pieces: list[str] = []
    buffer = ""
    for sentence in re.split(r"(?<=[.!?])\s+", text):
        if len(sentence) > max_chars:
            if buffer:
                pieces.append(buffer)
                buffer = ""
            pieces.extend(sentence[i : i + max_chars] for i in range(0, len(sentence), max_chars))
            continue
        candidate = f"{buffer} {sentence}".strip() if buffer else sentence
        if len(candidate) > max_chars:
            pieces.append(buffer)
            buffer = sentence
        else:
            buffer = candidate
    if buffer:
        pieces.append(buffer)
    return pieces


def _pack(paragraphs: list[str], min_chars: int, max_chars: int) -> list[str]:
    """Greedily pack paragraphs into chunks; merge a short tail into the previous one."""
    chunks: list[str] = []
    buffer = ""
    for paragraph in paragraphs:
        paragraph = paragraph.strip()
        if not paragraph:
            continue
        if len(paragraph) > max_chars:
            if buffer:
                chunks.append(buffer)
                buffer = ""
            chunks.extend(_split_long(paragraph, max_chars))
            continue
        candidate = f"{buffer}\n\n{paragraph}" if buffer else paragraph
        if buffer and len(candidate) > max_chars:
            chunks.append(buffer)
            buffer = paragraph
        else:
            buffer = candidate
    if buffer:
        chunks.append(buffer)

    merged: list[str] = []
    for chunk in chunks:
        if merged and len(merged[-1]) < min_chars and len(merged[-1]) + 2 + len(chunk) <= max_chars:
            merged[-1] = f"{merged[-1]}\n\n{chunk}"
        else:
            merged.append(chunk)
    return merged


def _render(title: str, heading: str | None, text: str) -> str:
    prefix = title if heading in (None, "", title) else f"{title}. {heading}"
    return f"{prefix}. {text}".strip()


def chunk_document(title: str, body: str) -> list[str]:
    """Split a document body into title-prefixed chunks of roughly 300–600 chars."""
    pieces: list[tuple[str | None, str]] = []
    for heading, text in _split_sections(body):
        paragraphs = [part.strip() for part in re.split(r"\n\s*\n", text) if part.strip()]
        if not paragraphs:
            continue
        prefix_length = len(_render(title, heading, ""))
        max_body = max(200, MAX_CHUNK_CHARS - prefix_length - 2)
        min_body = max(150, MIN_CHUNK_CHARS - prefix_length - 2)
        for piece in _pack(paragraphs, min_body, max_body):
            pieces.append((heading, piece))

    # Short sections are merged into a neighbour (heading kept inline) so the
    # stored chunk still clears the lower bound.
    merged: list[tuple[str | None, str]] = []
    for heading, text in pieces:
        incoming_length = len(_render(title, heading, text))
        if merged and incoming_length < MIN_CHUNK_CHARS:
            previous_heading, previous_text = merged[-1]
            inline = text
            if heading and heading not in (previous_heading, title):
                inline = f"{heading}. {text}"
            candidate = f"{previous_text}\n\n{inline}"
            if len(_render(title, previous_heading, candidate)) <= MAX_CHUNK_CHARS:
                merged[-1] = (previous_heading, candidate)
                continue
        merged.append((heading, text))

    return [_render(title, heading, text) for heading, text in merged] or [title]


def load_documents(docs_dir: Path | str = KB_DOCS_DIR) -> list[ParsedDocument]:
    """Read every `*.md` in the folder, sorted by filename (stable chunk ids)."""
    directory = Path(docs_dir)
    documents: list[ParsedDocument] = []
    for path in sorted(directory.glob("*.md")):
        raw = path.read_text(encoding="utf-8")
        meta, body = _parse_frontmatter(raw)
        title = meta.get("title") or _first_heading(body) or path.stem
        documents.append(
            ParsedDocument(
                title=title,
                source_url=meta.get("source_url") or f"https://kb.avito.internal/{path.stem}",
                content=body.strip(),
                keywords=meta.get("keywords", ""),
            )
        )
    return documents


async def ingest_documents(
    session: AsyncSession, docs_dir: Path | str = KB_DOCS_DIR
) -> IngestReport:
    """Upsert documents by title and rebuild chunks only when the source changed."""
    report = IngestReport()
    for document in load_documents(docs_dir):
        row = (
            await session.execute(select(KbDocument).where(KbDocument.title == document.title))
        ).scalar_one_or_none()
        changed = row is None
        if row is None:
            row = KbDocument(
                title=document.title,
                content=document.content,
                source_url=document.source_url,
                keywords=document.keywords,
            )
            session.add(row)
            await session.flush()
            report.created += 1
        elif (row.content, row.source_url, row.keywords) != (
            document.content,
            document.source_url,
            document.keywords,
        ):
            row.content = document.content
            row.source_url = document.source_url
            row.keywords = document.keywords
            changed = True
            report.updated += 1

        report.documents += 1
        if changed:
            await session.execute(delete(KbChunk).where(KbChunk.doc_id == row.id))
            chunks = chunk_document(document.title, document.content)
            for index, content in enumerate(chunks):
                session.add(
                    KbChunk(
                        doc_id=row.id,
                        chunk_index=index,
                        title=document.title,
                        content=content,
                    )
                )
            report.chunks += len(chunks)
        else:
            existing = await session.execute(select(KbChunk.id).where(KbChunk.doc_id == row.id))
            report.chunks += len(existing.all())

    await session.flush()
    return report
