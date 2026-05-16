"""add cases.taxonomy_id FK

Revision ID: 7c155524a515
Revises: bac221b0eb78
Create Date: 2026-05-15 09:03:01.378412

Sub-spec 02 Task 3: wires the deferred FK from cases.taxonomy_id to
security_taxonomies.id. Sub-spec 01 declared the column without a FK because
security_taxonomies didn't exist yet; now it does (Sub-spec 02 Task 1).
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '7c155524a515'
down_revision: Union[str, None] = 'bac221b0eb78'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_foreign_key(
        "fk_cases_taxonomy_id",
        "cases", "security_taxonomies",
        ["taxonomy_id"], ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_cases_taxonomy_id", "cases", type_="foreignkey")
