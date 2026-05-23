"""add n8n_workflow_id link to n8n_workflows catalog

Revision ID: c4b7e9f1a3d2
Revises: f2a8b9c3d4e5
Create Date: 2026-05-23

Adds a nullable column that points each CMS catalog row at the actual
workflow inside n8n (the short id like "F7v469lghiBA7FcX" that the
n8n REST API returns). Required by the n8n_inventory feature so we
can tell registered workflows from "orphans" (live in n8n but not in
CMS catalog).

Nullable so existing rows survive the upgrade; operator + the WCR
implement action populate the field as workflows get linked.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c4b7e9f1a3d2"
down_revision: Union[str, None] = "f2a8b9c3d4e5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "n8n_workflows",
        sa.Column("n8n_workflow_id", sa.String(length=64), nullable=True),
    )
    op.create_index(
        "ix_n8n_workflows_n8n_id",
        "n8n_workflows",
        ["n8n_workflow_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_n8n_workflows_n8n_id", table_name="n8n_workflows")
    op.drop_column("n8n_workflows", "n8n_workflow_id")
