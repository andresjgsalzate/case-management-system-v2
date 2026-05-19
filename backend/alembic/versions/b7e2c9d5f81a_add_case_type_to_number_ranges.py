"""add case_type to case_number_ranges

Revision ID: b7e2c9d5f81a
Revises: d4a8b2c1e6f5
Create Date: 2026-05-19

Adds case_type column so admins can register prefixes per (tenant, case_type)
with per-tenant localization. Backfill maps current prefixes to the legacy
hardcoded mapping (REQ→request, INC→incident, EVT→event); anything else
defaults to 'request' and ops team must reconcile manually.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b7e2c9d5f81a'
down_revision: Union[str, None] = 'd4a8b2c1e6f5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add column NULLABLE so existing rows survive the ALTER.
    op.add_column(
        'case_number_ranges',
        sa.Column('case_type', sa.String(length=20), nullable=True),
    )

    # 2. Backfill: legacy hardcoded mapping in cases/use_cases.py was
    #    REQ→request, INC→incident, EVT→event. Anything else gets
    #    'request' as a safe default — ops team should review.
    op.execute("""
        UPDATE case_number_ranges
        SET case_type = CASE
            WHEN UPPER(prefix) = 'REQ' THEN 'request'
            WHEN UPPER(prefix) = 'INC' THEN 'incident'
            WHEN UPPER(prefix) = 'EVT' THEN 'event'
            ELSE 'request'
        END
        WHERE case_type IS NULL
    """)

    # 3. Now make it NOT NULL.
    op.alter_column(
        'case_number_ranges', 'case_type',
        existing_type=sa.String(length=20),
        nullable=False,
    )

    # 4. Add check constraint + index.
    op.create_check_constraint(
        'ck_case_number_range_case_type',
        'case_number_ranges',
        "case_type IN ('request', 'incident', 'event')",
    )
    op.create_index(
        op.f('ix_case_number_ranges_case_type'),
        'case_number_ranges',
        ['case_type'],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f('ix_case_number_ranges_case_type'),
        table_name='case_number_ranges',
    )
    op.drop_constraint(
        'ck_case_number_range_case_type',
        'case_number_ranges',
        type_='check',
    )
    op.drop_column('case_number_ranges', 'case_type')
