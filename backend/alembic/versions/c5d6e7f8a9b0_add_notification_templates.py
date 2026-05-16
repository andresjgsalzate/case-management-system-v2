"""add notification_templates

Revision ID: c5d6e7f8a9b0
Revises: b3c4d5e6f7a8
Create Date: 2026-04-09
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "c5d6e7f8a9b0"
down_revision = "b3c4d5e6f7a8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "notification_templates",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("event_name", sa.String(100), nullable=False, unique=True),
        sa.Column("notification_type", sa.String(50), nullable=False),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("body", sa.Text, nullable=False),
        sa.Column("is_enabled", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("variables", sa.JSON, nullable=False, server_default="[]"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_notification_templates_event_name", "notification_templates", ["event_name"])


def downgrade() -> None:
    op.drop_index("ix_notification_templates_event_name", "notification_templates")
    op.drop_table("notification_templates")
