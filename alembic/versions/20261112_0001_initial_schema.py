"""initial schema

Revision ID: 20261112_0001
Revises:
Create Date: 2026-11-12

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20261112_0001"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "funnels",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("slug", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
    )
    op.create_index("ix_funnels_slug", "funnels", ["slug"])

    op.create_table(
        "funnel_stages",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("funnel_id", sa.Integer(), nullable=False),
        sa.Column("slug", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["funnel_id"], ["funnels.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("funnel_id", "slug", name="uq_funnel_stage_slug"),
    )
    op.create_index("ix_funnel_stages_funnel_id", "funnel_stages", ["funnel_id"])

    op.create_table(
        "leads",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("funnel_id", sa.Integer(), nullable=True),
        sa.Column("stage_slug", sa.String(length=64), nullable=True),
        sa.Column("name", sa.String(length=120), nullable=True),
        sa.Column("phone", sa.String(length=32), nullable=True),
        sa.Column("email", sa.String(length=160), nullable=True),
        sa.Column("telegram_id", sa.String(length=64), nullable=True),
        sa.Column("telegram_username", sa.String(length=64), nullable=True),
        sa.Column("need", sa.Text(), nullable=True),
        sa.Column("budget_note", sa.String(length=120), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["funnel_id"], ["funnels.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_leads_source", "leads", ["source"])
    op.create_index("ix_leads_status", "leads", ["status"])
    op.create_index("ix_leads_funnel_id", "leads", ["funnel_id"])
    op.create_index("ix_leads_telegram_id", "leads", ["telegram_id"])

    op.create_table(
        "conversation_messages",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("lead_id", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_conversation_messages_lead_id", "conversation_messages", ["lead_id"])

    op.create_table(
        "audit_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("actor", sa.String(length=64), nullable=False),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("entity_type", sa.String(length=64), nullable=False),
        sa.Column("entity_id", sa.String(length=64), nullable=True),
        sa.Column("payload", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_events_action", "audit_events", ["action"])

    op.create_table(
        "admin_users",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("username", sa.String(length=64), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("is_active", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("username"),
    )
    op.create_index("ix_admin_users_username", "admin_users", ["username"])

    op.create_table(
        "outbox_jobs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("kind", sa.String(length=64), nullable=False),
        sa.Column("payload", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("available_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_outbox_jobs_kind", "outbox_jobs", ["kind"])
    op.create_index("ix_outbox_jobs_status", "outbox_jobs", ["status"])


def downgrade() -> None:
    op.drop_table("outbox_jobs")
    op.drop_table("admin_users")
    op.drop_table("audit_events")
    op.drop_table("conversation_messages")
    op.drop_table("leads")
    op.drop_table("funnel_stages")
    op.drop_table("funnels")
