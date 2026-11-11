"""kb_chunks table

Revision ID: 0003_kb_chunks
Revises: 0002_kb_sources
Create Date: 2026-11-11
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0003_kb_chunks"
down_revision = "0002_kb_sources"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "kb_chunks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "doc_id",
            sa.Integer(),
            sa.ForeignKey("kb_documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.UniqueConstraint("doc_id", "chunk_index", name="uq_kb_chunks_doc_index"),
    )
    op.create_index("ix_kb_chunks_doc_id", "kb_chunks", ["doc_id"])


def downgrade() -> None:
    op.drop_index("ix_kb_chunks_doc_id", table_name="kb_chunks")
    op.drop_table("kb_chunks")
