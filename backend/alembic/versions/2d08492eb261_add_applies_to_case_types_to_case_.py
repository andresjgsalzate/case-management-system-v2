"""add applies_to_case_types to case_statuses

Revision ID: 2d08492eb261
Revises: 9ae174d08d77
Create Date: 2026-05-13 17:08:24.304395

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2d08492eb261'
down_revision: Union[str, None] = '9ae174d08d77'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "case_statuses",
        sa.Column(
            "applies_to_case_types",
            sa.JSON,
            nullable=False,
            server_default=sa.text("'[\"request\", \"incident\", \"event\"]'::json"),
        ),
    )


def downgrade() -> None:
    op.drop_column("case_statuses", "applies_to_case_types")
