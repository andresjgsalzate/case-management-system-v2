"""helpdesk levels and transfers

Revision ID: c1d2e3f4a5b6
Revises: a3b4c5d6e7f8
Create Date: 2026-04-18
"""
from alembic import op
import sqlalchemy as sa

revision = "c1d2e3f4a5b6"
down_revision = "a3b4c5d6e7f8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "roles",
        sa.Column("level", sa.Integer(), nullable=False, server_default="1"),
    )
    op.create_check_constraint("roles_level_non_negative", "roles", "level >= 0")
    op.create_index("idx_roles_level", "roles", ["level"])

    op.add_column(
        "cases",
        sa.Column("current_level", sa.Integer(), nullable=False, server_default="1"),
    )
    op.create_check_constraint("cases_current_level_positive", "cases", "current_level >= 1")
    op.create_index("idx_cases_current_level", "cases", ["current_level"])

    op.create_table(
        "case_transfers",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=True),
        sa.Column("case_id", sa.String(36), sa.ForeignKey("cases.id", ondelete="CASCADE"), nullable=False),
        sa.Column("from_user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("from_level", sa.Integer(), nullable=False),
        sa.Column("to_user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("to_team_id", sa.String(36), sa.ForeignKey("teams.id"), nullable=False),
        sa.Column("to_level", sa.Integer(), nullable=False),
        sa.Column("transfer_type", sa.String(16), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "transfer_type IN ('escalate','reassign','de-escalate')",
            name="transfers_type_valid",
        ),
        sa.CheckConstraint(
            "length(trim(reason)) > 0",
            name="transfers_reason_nonempty",
        ),
    )
    op.create_index(
        "idx_case_transfers_case_id",
        "case_transfers",
        ["case_id", "created_at"],
    )
    op.create_index(
        "idx_case_transfers_tenant_id",
        "case_transfers",
        ["tenant_id"],
    )


def downgrade() -> None:
    op.drop_index("idx_case_transfers_tenant_id", table_name="case_transfers")
    op.drop_index("idx_case_transfers_case_id", table_name="case_transfers")
    op.drop_table("case_transfers")

    op.drop_index("idx_cases_current_level", table_name="cases")
    op.drop_constraint("cases_current_level_positive", "cases", type_="check")
    op.drop_column("cases", "current_level")

    op.drop_index("idx_roles_level", table_name="roles")
    op.drop_constraint("roles_level_non_negative", "roles", type_="check")
    op.drop_column("roles", "level")
