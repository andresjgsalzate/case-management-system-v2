"""redesign dispositions fields

Revision ID: e7f8a9b0c1d2
Revises: d6e7f8a9b0c1
Create Date: 2026-04-14 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = "e7f8a9b0c1d2"
down_revision = "d6e7f8a9b0c1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add new columns
    op.add_column("dispositions", sa.Column("date", sa.Date(), nullable=True))
    op.add_column("dispositions", sa.Column("case_number", sa.String(50), nullable=True, index=True))
    op.add_column("dispositions", sa.Column("item_name", sa.String(500), nullable=True))
    op.add_column("dispositions", sa.Column("storage_path", sa.String(1000), nullable=True))
    op.add_column("dispositions", sa.Column("revision_number", sa.String(200), nullable=True))
    op.add_column("dispositions", sa.Column("observations", sa.Text(), nullable=True))

    # Make title and content nullable (they were NOT NULL, now optional)
    op.alter_column("dispositions", "title", existing_type=sa.String(500), nullable=True)
    op.alter_column("dispositions", "content", existing_type=sa.Text(), nullable=True)


def downgrade() -> None:
    op.drop_column("dispositions", "observations")
    op.drop_column("dispositions", "revision_number")
    op.drop_column("dispositions", "storage_path")
    op.drop_column("dispositions", "item_name")
    op.drop_column("dispositions", "case_number")
    op.drop_column("dispositions", "date")

    op.alter_column("dispositions", "title", existing_type=sa.String(500), nullable=False)
    op.alter_column("dispositions", "content", existing_type=sa.Text(), nullable=False)
