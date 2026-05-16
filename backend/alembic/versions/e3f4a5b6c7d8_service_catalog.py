"""service catalog: categories, items, fields, case custom values

Revision ID: e3f4a5b6c7d8
Revises: d2e3f4a5b6c7
Create Date: 2026-04-24
"""
from alembic import op
import sqlalchemy as sa


revision = "e3f4a5b6c7d8"
down_revision = "d2e3f4a5b6c7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # service_catalog_categories
    op.create_table(
        "service_catalog_categories",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=True, index=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("slug", sa.String(100), nullable=False),
        sa.Column("description", sa.String(1000), nullable=True),
        sa.Column("icon", sa.String(50), nullable=True),
        sa.Column("color", sa.String(20), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("tenant_id", "slug", name="uq_svc_category_tenant_slug"),
    )

    # service_catalog_items
    op.create_table(
        "service_catalog_items",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=True, index=True),
        sa.Column(
            "category_id",
            sa.String(36),
            sa.ForeignKey("service_catalog_categories.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("slug", sa.String(100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "default_priority_id",
            sa.String(36),
            sa.ForeignKey("case_priorities.id"),
            nullable=True,
        ),
        sa.Column(
            "default_team_id",
            sa.String(36),
            sa.ForeignKey("teams.id"),
            nullable=True,
        ),
        sa.Column("default_level", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "sla_policy_id",
            sa.String(36),
            sa.ForeignKey("sla_policies.id"),
            nullable=True,
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("tenant_id", "slug", name="uq_svc_item_tenant_slug"),
        sa.CheckConstraint("default_level >= 0", name="ck_svc_item_level_non_negative"),
    )

    # service_catalog_fields
    op.create_table(
        "service_catalog_fields",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=True, index=True),
        sa.Column(
            "item_id",
            sa.String(36),
            sa.ForeignKey("service_catalog_items.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("field_key", sa.String(80), nullable=False),
        sa.Column("label", sa.String(200), nullable=False),
        sa.Column("field_type", sa.String(20), nullable=False),
        sa.Column("is_required", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("placeholder", sa.String(200), nullable=True),
        sa.Column("help_text", sa.String(500), nullable=True),
        sa.Column("options", sa.JSON(), nullable=True),
        sa.Column("validation", sa.JSON(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("item_id", "field_key", name="uq_svc_field_item_key"),
        sa.CheckConstraint(
            "field_type IN ('text','textarea','number','date','datetime',"
            "'select','radio','checkbox','multiselect','email','phone')",
            name="ck_svc_field_type_valid",
        ),
    )

    # cases.service_item_id
    op.add_column(
        "cases",
        sa.Column(
            "service_item_id",
            sa.String(36),
            sa.ForeignKey("service_catalog_items.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index("idx_cases_service_item_id", "cases", ["service_item_id"])

    # case_custom_values
    op.create_table(
        "case_custom_values",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=True, index=True),
        sa.Column(
            "case_id",
            sa.String(36),
            sa.ForeignKey("cases.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "field_id",
            sa.String(36),
            sa.ForeignKey("service_catalog_fields.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("value", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("case_id", "field_id", name="uq_case_custom_value_case_field"),
    )


def downgrade() -> None:
    op.drop_table("case_custom_values")
    op.drop_index("idx_cases_service_item_id", table_name="cases")
    op.drop_column("cases", "service_item_id")
    op.drop_table("service_catalog_fields")
    op.drop_table("service_catalog_items")
    op.drop_table("service_catalog_categories")
