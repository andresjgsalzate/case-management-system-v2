"""merge kb_enhancements with case_resolution_requests

Revision ID: 1f35f05d8d94
Revises: b8d9e0f1a2b3, d5e6f7a8b9c0
Create Date: 2026-04-17 22:10:31.703318

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1f35f05d8d94'
down_revision: Union[str, None] = ('b8d9e0f1a2b3', 'd5e6f7a8b9c0')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
