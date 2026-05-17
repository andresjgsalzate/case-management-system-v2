"""add velo_org_id to tenants

Revision ID: b56fda7a38c6
Revises: 5308b8cc935f
Create Date: 2026-05-17 03:25:32.412735

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b56fda7a38c6'
down_revision: Union[str, None] = '5308b8cc935f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'tenants',
        sa.Column('velo_org_id', sa.String(length=80), nullable=True),
    )
    op.create_unique_constraint(
        'uq_tenants_velo_org_id',
        'tenants',
        ['velo_org_id'],
    )


def downgrade() -> None:
    op.drop_constraint('uq_tenants_velo_org_id', 'tenants', type_='unique')
    op.drop_column('tenants', 'velo_org_id')
