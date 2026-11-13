"""reminders table + checklist_progress.started_at

Revision ID: 0004_reminders
Revises: 0003_kb_chunks
Create Date: 2026-11-13
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0004_reminders"
down_revision = "0003_kb_chunks"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Existing rows get "now": the cron counts overdue days from this stamp, and
    # backfilling with the template creation date would mark the whole checklist
    # overdue on the first deploy.
    op.add_column(
        "checklist_progress",
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_table(
        "reminders",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "checklist_item_id",
            sa.Integer(),
            sa.ForeignKey("checklist_items.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("acked_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_reminders_user_id", "reminders", ["user_id"])
    op.create_index("ix_reminders_checklist_item_id", "reminders", ["checklist_item_id"])


def downgrade() -> None:
    op.drop_index("ix_reminders_checklist_item_id", table_name="reminders")
    op.drop_index("ix_reminders_user_id", table_name="reminders")
    op.drop_table("reminders")
    op.drop_column("checklist_progress", "started_at")
