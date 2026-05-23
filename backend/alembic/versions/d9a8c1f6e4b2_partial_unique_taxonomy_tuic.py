"""partial unique tuic_code (active only) on security_taxonomies

Revision ID: d9a8c1f6e4b2
Revises: c4b7e9f1a3d2
Create Date: 2026-05-23

The original UniqueConstraint (tenant_id, tuic_code) blocks reusing a
tuic_code after a soft-delete -- inactive rows still occupy the slot.
We replace it with a partial unique index that only counts active rows,
so soft-deleting "SPAM" frees the code for a new taxonomy without
losing the audit trail of the original row.

NULL semantics: Postgres treats NULL as distinct in unique indexes
(unless NULLS NOT DISTINCT), so global rows (tenant_id IS NULL) keep
the same effective behaviour they had with the full constraint -- the
app-layer check in _tuic_code_exists is what actually guards globals.
"""
from alembic import op


revision = "d9a8c1f6e4b2"
down_revision = "c4b7e9f1a3d2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint(
        "uq_taxonomy_tenant_tuic",
        "security_taxonomies",
        type_="unique",
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_taxonomy_tenant_tuic_active "
        "ON security_taxonomies (tenant_id, tuic_code) "
        "WHERE is_active = TRUE"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_taxonomy_tenant_tuic_active")
    op.create_unique_constraint(
        "uq_taxonomy_tenant_tuic",
        "security_taxonomies",
        ["tenant_id", "tuic_code"],
    )
