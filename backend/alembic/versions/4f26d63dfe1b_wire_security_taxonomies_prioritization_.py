"""wire security_taxonomies.prioritization_formula_id FK

Revision ID: 4f26d63dfe1b
Revises: 3e2c2ec1cb76
Create Date: 2026-05-15 21:21:53.148259

Sub-spec 03 Task 2: wires the deferred FK from
security_taxonomies.prioritization_formula_id → prioritization_formulas.id.
Sub-spec 02 declared the column without a FK because prioritization_formulas
did not exist yet; now it does (Sub-spec 03 Task 1).
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '4f26d63dfe1b'
down_revision: Union[str, None] = '3e2c2ec1cb76'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_foreign_key(
        "fk_security_taxonomies_prioritization_formula_id",
        "security_taxonomies", "prioritization_formulas",
        ["prioritization_formula_id"], ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_security_taxonomies_prioritization_formula_id",
        "security_taxonomies", type_="foreignkey",
    )
