"""add email config tables

Revision ID: d6e7f8a9b0c1
Revises: c5d6e7f8a9b0
Create Date: 2026-04-14
"""
from alembic import op
import sqlalchemy as sa

revision = "d6e7f8a9b0c1"
down_revision = "c5d6e7f8a9b0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "smtp_config",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("host", sa.String(255), nullable=False, server_default=""),
        sa.Column("port", sa.Integer, nullable=False, server_default="587"),
        sa.Column("username", sa.String(255), nullable=True),
        sa.Column("password", sa.Text, nullable=True),
        sa.Column("from_email", sa.String(255), nullable=False, server_default="noreply@example.com"),
        sa.Column("from_name", sa.String(255), nullable=False, server_default="CaseManager"),
        sa.Column("use_tls", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("is_enabled", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
    )
    op.create_table(
        "email_templates",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("scope", sa.String(100), nullable=False),
        sa.Column("blocks", sa.JSON, nullable=False, server_default="[]"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
    )
    op.create_index("ix_email_templates_scope", "email_templates", ["scope"])


def downgrade() -> None:
    op.drop_index("ix_email_templates_scope", "email_templates")
    op.drop_table("email_templates")
    op.drop_table("smtp_config")
