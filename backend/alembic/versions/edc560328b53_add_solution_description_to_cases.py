"""add solution_description to cases

Revision ID: edc560328b53
Revises: f9a0b1c2d3e4
Create Date: 2026-04-15
"""
from alembic import op
import sqlalchemy as sa

revision = "edc560328b53"
down_revision = "f9a0b1c2d3e4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("cases", sa.Column("solution_description", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("cases", "solution_description")
