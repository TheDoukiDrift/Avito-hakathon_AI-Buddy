"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-11-10
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None

USER_ROLE = sa.Enum(
    "intern", "mentor", "manager", "hr_bp", name="user_role", native_enum=False, length=32
)
PROGRESS_STATUS = sa.Enum(
    "pending", "done", name="progress_status", native_enum=False, length=32
)
ABSENCE_TYPE = sa.Enum(
    "day_off", "vacation", "sick", name="absence_type", native_enum=False, length=32
)
ABSENCE_STATUS = sa.Enum(
    "draft",
    "pending_approval",
    "approved",
    "rejected",
    name="absence_status",
    native_enum=False,
    length=32,
)
MESSAGE_ROLE = sa.Enum("user", "assistant", name="message_role", native_enum=False, length=32)


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("role", USER_ROLE, nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column("team", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "checklist_templates",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "checklist_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "template_id",
            sa.Integer(),
            sa.ForeignKey("checklist_templates.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("week", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("position", sa.Integer(), nullable=False),
    )
    op.create_index("ix_checklist_items_template_id", "checklist_items", ["template_id"])

    op.create_table(
        "checklist_progress",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "item_id",
            sa.Integer(),
            sa.ForeignKey("checklist_items.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("status", PROGRESS_STATUS, nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("user_id", "item_id", name="uq_progress_user_item"),
    )
    op.create_index("ix_checklist_progress_user_id", "checklist_progress", ["user_id"])
    op.create_index("ix_checklist_progress_item_id", "checklist_progress", ["item_id"])

    op.create_table(
        "absence_requests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("type", ABSENCE_TYPE, nullable=False),
        sa.Column("date_from", sa.Date(), nullable=False),
        sa.Column("date_to", sa.Date(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("status", ABSENCE_STATUS, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "decided_by",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_absence_requests_user_id", "absence_requests", ["user_id"])

    op.create_table(
        "contacts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=255), nullable=False),
        sa.Column("team", sa.String(length=255), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=False),
    )
    op.create_index("ix_contacts_team", "contacts", ["team"])

    op.create_table(
        "conversations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_conversations_user_id", "conversations", ["user_id"])

    op.create_table(
        "messages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "conversation_id",
            sa.Integer(),
            sa.ForeignKey("conversations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", MESSAGE_ROLE, nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("tool_calls", sa.JSON(), nullable=True),
    )
    op.create_index("ix_messages_conversation_id", "messages", ["conversation_id"])

    op.create_table(
        "audit_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True
        ),
        sa.Column("action", sa.String(length=255), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_audit_events_user_id", "audit_events", ["user_id"])
    op.create_index("ix_audit_events_action", "audit_events", ["action"])


def downgrade() -> None:
    for table in (
        "audit_events",
        "messages",
        "conversations",
        "contacts",
        "absence_requests",
        "checklist_progress",
        "checklist_items",
        "checklist_templates",
        "users",
    ):
        op.drop_table(table)
