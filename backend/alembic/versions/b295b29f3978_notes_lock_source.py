"""Add is_locked + source columns to case_notes for SOC2 audit notes

Revision ID: b295b29f3978
Revises: e2a7c3f9b1d4
Create Date: 2026-05-28 18:51:19.570522

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'b295b29f3978'
down_revision: Union[str, None] = 'e2a7c3f9b1d4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('case_notes', sa.Column('is_locked', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('case_notes', sa.Column('source', sa.String(length=20), nullable=False, server_default='user'))
    op.create_check_constraint(
        'ck_case_notes_source',
        'case_notes',
        "source IN ('user', 'system')",
    )


def downgrade() -> None:
    op.drop_constraint('ck_case_notes_source', 'case_notes', type_='check')
    op.drop_column('case_notes', 'source')
    op.drop_column('case_notes', 'is_locked')
