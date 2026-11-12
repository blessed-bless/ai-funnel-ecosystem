"""workspace managers timeline soft-delete

Revision ID: 20261112_0003
Revises: 20261112_0002
Create Date: 2026-11-12

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20261112_0003"
down_revision: Union[str, Sequence[str], None] = "20261112_0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "workspaces",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("slug", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("is_active", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
    )
    op.create_index("ix_workspaces_slug", "workspaces", ["slug"])

    op.create_table(
        "managers",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("workspace_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("telegram_chat_id", sa.String(length=64), nullable=True),
        sa.Column("is_active", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_managers_workspace_id", "managers", ["workspace_id"])

    op.create_table(
        "lead_activities",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("lead_id", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=64), nullable=False),
        sa.Column("actor", sa.String(length=64), nullable=False, server_default="system"),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("meta_json", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["lead_id"], ["leads.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_lead_activities_lead_id", "lead_activities", ["lead_id"])
    op.create_index("ix_lead_activities_kind", "lead_activities", ["kind"])

    with op.batch_alter_table("leads") as batch:
        batch.add_column(sa.Column("workspace_id", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("assigned_manager_id", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("phone_normalized", sa.String(length=32), nullable=True))
        batch.add_column(sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
        batch.create_index("ix_leads_workspace_id", ["workspace_id"])
        batch.create_index("ix_leads_assigned_manager_id", ["assigned_manager_id"])
        batch.create_index("ix_leads_phone_norm", ["phone_normalized"])
        batch.create_index("ix_leads_deleted_at", ["deleted_at"])
        batch.create_index("ix_leads_workspace_status", ["workspace_id", "status"])

    with op.batch_alter_table("funnels") as batch:
        batch.add_column(sa.Column("workspace_id", sa.Integer(), nullable=True))
        batch.create_index("ix_funnels_workspace_id", ["workspace_id"])


def downgrade() -> None:
    with op.batch_alter_table("funnels") as batch:
        batch.drop_index("ix_funnels_workspace_id")
        batch.drop_column("workspace_id")

    with op.batch_alter_table("leads") as batch:
        batch.drop_index("ix_leads_workspace_status")
        batch.drop_index("ix_leads_deleted_at")
        batch.drop_index("ix_leads_phone_norm")
        batch.drop_index("ix_leads_assigned_manager_id")
        batch.drop_index("ix_leads_workspace_id")
        batch.drop_column("deleted_at")
        batch.drop_column("phone_normalized")
        batch.drop_column("assigned_manager_id")
        batch.drop_column("workspace_id")

    op.drop_index("ix_lead_activities_kind", table_name="lead_activities")
    op.drop_index("ix_lead_activities_lead_id", table_name="lead_activities")
    op.drop_table("lead_activities")
    op.drop_index("ix_managers_workspace_id", table_name="managers")
    op.drop_table("managers")
    op.drop_index("ix_workspaces_slug", table_name="workspaces")
    op.drop_table("workspaces")
