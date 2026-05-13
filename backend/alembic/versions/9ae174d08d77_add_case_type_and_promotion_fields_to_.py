"""add case_type and promotion fields to cases

Revision ID: 9ae174d08d77
Revises: a5b6c7d8e9f0
Create Date: 2026-05-13 17:03:44.548446

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9ae174d08d77'
down_revision: Union[str, None] = 'a5b6c7d8e9f0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # New columns on cases
    op.add_column(
        "cases",
        sa.Column("case_type", sa.String(20), nullable=False, server_default="request"),
    )
    op.add_column(
        "cases",
        sa.Column("taxonomy_id", sa.String(36), nullable=True),
    )
    op.add_column(
        "cases",
        sa.Column("original_case_number", sa.String(50), nullable=True),
    )
    op.add_column(
        "cases",
        sa.Column("original_case_type", sa.String(20), nullable=True),
    )
    op.add_column(
        "cases",
        sa.Column("promoted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "cases",
        sa.Column(
            "promoted_by",
            sa.String(36),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
    )
    op.add_column(
        "cases",
        sa.Column("pending_triage_until", sa.DateTime(timezone=True), nullable=True),
    )

    # Indexes for query performance
    op.create_index("ix_cases_case_type", "cases", ["case_type"])
    op.create_index("ix_cases_taxonomy_id", "cases", ["taxonomy_id"])
    op.create_index(
        "ix_cases_original_case_number", "cases", ["original_case_number"]
    )

    # CheckConstraints
    op.create_check_constraint(
        "ck_cases_case_type_valid",
        "cases",
        "case_type IN ('request', 'incident', 'event')",
    )
    op.create_check_constraint(
        "ck_cases_promotion_consistency",
        "cases",
        "(promoted_at IS NULL AND original_case_number IS NULL AND original_case_type IS NULL) "
        "OR (promoted_at IS NOT NULL AND original_case_number IS NOT NULL AND original_case_type IS NOT NULL)",
    )


def downgrade() -> None:
    op.drop_constraint("ck_cases_promotion_consistency", "cases", type_="check")
    op.drop_constraint("ck_cases_case_type_valid", "cases", type_="check")
    op.drop_index("ix_cases_original_case_number", table_name="cases")
    op.drop_index("ix_cases_taxonomy_id", table_name="cases")
    op.drop_index("ix_cases_case_type", table_name="cases")
    op.drop_column("cases", "pending_triage_until")
    op.drop_column("cases", "promoted_by")
    op.drop_column("cases", "promoted_at")
    op.drop_column("cases", "original_case_type")
    op.drop_column("cases", "original_case_number")
    op.drop_column("cases", "taxonomy_id")
    op.drop_column("cases", "case_type")
