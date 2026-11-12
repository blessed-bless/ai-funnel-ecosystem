"""notes tags webhook deliveries

Revision ID: 20261112_0002
Revises: 20261112_0001
Create Date: 2026-11-12

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20261112_0002"
down_revision: Union[str, Sequence[str], None] = "20261112_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("leads") as batch:
        batch.add_column(sa.Column("tags", sa.String(length=255), nullable=True))
        batch.create_index("ix_leads_phone", ["phone"])
        batch.create_index("ix_leads_status_updated", ["status", "updated_at"])

    op.create_table(
        "lead_notes",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("lead_id", sa.Integer(), nullable=False),
        sa.Column("author", sa.String(length=64), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["lead_id"], ["leads.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_lead_notes_lead_id", "lead_notes", ["lead_id"])

    op.create_table(
        "webhook_deliveries",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("event", sa.String(length=64), nullable=False),
        sa.Column("target", sa.String(length=255), nullable=False),
        sa.Column("status_code", sa.Integer(), nullable=False),
        sa.Column("success", sa.Integer(), nullable=False),
        sa.Column("response_body", sa.Text(), nullable=True),
        sa.Column("payload", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_webhook_deliveries_event", "webhook_deliveries", ["event"])


def downgrade() -> None:
    op.drop_table("webhook_deliveries")
    op.drop_table("lead_notes")
    with op.batch_alter_table("leads") as batch:
        batch.drop_index("ix_leads_status_updated")
        batch.drop_index("ix_leads_phone")
        batch.drop_column("tags")
