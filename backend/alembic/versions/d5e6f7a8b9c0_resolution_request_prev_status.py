"""add previous_status_id to case_resolution_requests

Revision ID: d5e6f7a8b9c0
Revises: c4d5e6f7a8b9
Create Date: 2026-04-15
"""
from alembic import op
import sqlalchemy as sa

revision = "d5e6f7a8b9c0"
down_revision = "c4d5e6f7a8b9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "case_resolution_requests",
        sa.Column("previous_status_id", sa.String(36), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("case_resolution_requests", "previous_status_id")
