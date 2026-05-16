"""sla_integration_config

Revision ID: a1b2c3d4e5f6
Revises: 95943f3f1e5b
Create Date: 2026-04-08 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = "a1b2c3d4e5f6"
down_revision = "95943f3f1e5b"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sla_integration_config",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("tenant_id", sa.String(36), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("pause_on_timer", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("low_max_hours", sa.Float(), nullable=True),
        sa.Column("medium_max_hours", sa.Float(), nullable=True),
        sa.Column("high_max_hours", sa.Float(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", name="uq_sla_integration_config_tenant"),
    )

    op.add_column(
        "sla_records",
        sa.Column("paused_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "sla_records",
        sa.Column(
            "total_paused_seconds",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )


def downgrade() -> None:
    op.drop_column("sla_records", "total_paused_seconds")
    op.drop_column("sla_records", "paused_at")
    op.drop_table("sla_integration_config")
