"""drop tenant_id FK on service_catalog tables

Revision ID: f4a5b6c7d8e9
Revises: e3f4a5b6c7d8
Create Date: 2026-04-25

The convention in this codebase is that tenant_id is a String(36) sentinel
without an enforced FK to tenants(id), because the app uses literal "default"
when no tenant is set. The previous migration created strict FKs that block
inserts in tenant-less environments. This migration relaxes them to match
the rest of the codebase.
"""
from alembic import op


revision = "f4a5b6c7d8e9"
down_revision = "e3f4a5b6c7d8"
branch_labels = None
depends_on = None


_TARGETS = [
    "service_catalog_categories",
    "service_catalog_items",
    "service_catalog_fields",
    "case_custom_values",
]


def upgrade() -> None:
    for table in _TARGETS:
        op.drop_constraint(f"{table}_tenant_id_fkey", table, type_="foreignkey")


def downgrade() -> None:
    for table in _TARGETS:
        op.create_foreign_key(
            f"{table}_tenant_id_fkey",
            table,
            "tenants",
            ["tenant_id"],
            ["id"],
        )
