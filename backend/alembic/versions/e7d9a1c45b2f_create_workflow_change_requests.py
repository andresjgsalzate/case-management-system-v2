"""create workflow_change_requests

Revision ID: e7d9a1c45b2f
Revises: a09b4d3e7f12
Create Date: 2026-05-22

Sub-spec 09 §3.9 Task 4.1: SOC2 compensating-control tracker so
admins without `n8n_editor:access` can propose workflow changes
auditably while CMS stays on n8n Community.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e7d9a1c45b2f"
down_revision: Union[str, None] = "a09b4d3e7f12"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "workflow_change_requests",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=True),
        sa.Column("workflow_id", sa.String(length=36), nullable=True),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("proposed_change", sa.JSON(), nullable=False),
        sa.Column("requested_by", sa.String(length=36), nullable=False),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "status",
            sa.String(length=20),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("reviewed_by", sa.String(length=36), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("review_notes", sa.Text(), nullable=True),
        sa.Column("implemented_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "implemented_in_workflow_url",
            sa.String(length=500),
            nullable=True,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["workflow_id"], ["n8n_workflows.id"], ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(["requested_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["reviewed_by"], ["users.id"]),
        sa.CheckConstraint(
            "status IN ('pending', 'in_review', 'approved', 'rejected', 'implemented')",
            name="ck_wcr_status",
        ),
    )
    op.create_index(
        "ix_workflow_change_requests_tenant_id",
        "workflow_change_requests",
        ["tenant_id"],
        unique=False,
    )
    op.create_index(
        "ix_workflow_change_requests_requested_by",
        "workflow_change_requests",
        ["requested_by"],
        unique=False,
    )
    op.create_index(
        "ix_wcr_status_requested",
        "workflow_change_requests",
        ["status", "requested_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_wcr_status_requested", table_name="workflow_change_requests")
    op.drop_index(
        "ix_workflow_change_requests_requested_by",
        table_name="workflow_change_requests",
    )
    op.drop_index(
        "ix_workflow_change_requests_tenant_id",
        table_name="workflow_change_requests",
    )
    op.drop_table("workflow_change_requests")
