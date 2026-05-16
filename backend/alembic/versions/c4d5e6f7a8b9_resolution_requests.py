"""add case_resolution_requests table

Revision ID: c4d5e6f7a8b9
Revises: a2b3c4d5e6f7
Create Date: 2026-04-15
"""
from alembic import op
import sqlalchemy as sa

revision = "c4d5e6f7a8b9"
down_revision = "a2b3c4d5e6f7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "case_resolution_requests",
        sa.Column("id",               sa.String(36),  primary_key=True),
        sa.Column("case_id",          sa.String(36),  sa.ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("tenant_id",        sa.String(36),  nullable=True),
        sa.Column("chat_message_id",  sa.String(36),  sa.ForeignKey("chat_messages.id"), nullable=True),
        sa.Column("requested_by",     sa.String(36),  sa.ForeignKey("users.id"), nullable=False),
        sa.Column("requested_at",     sa.DateTime(timezone=True), nullable=False),
        sa.Column("status",           sa.String(20),  nullable=False, server_default="pending"),
        sa.Column("responded_by",     sa.String(36),  sa.ForeignKey("users.id"), nullable=True),
        sa.Column("responded_at",     sa.DateTime(timezone=True), nullable=True),
        sa.Column("rating",           sa.SmallInteger(), nullable=True),
        sa.Column("observation",      sa.Text(),      nullable=True),
    )


def downgrade() -> None:
    op.drop_table("case_resolution_requests")
