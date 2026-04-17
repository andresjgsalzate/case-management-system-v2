"""add kb_document_types table, seed 4 base types, add FK from kb_articles

Revision ID: b7c8d9e0f1a2
Revises: b1c2d3e4f5a6
Create Date: 2026-04-17
"""
import uuid
from alembic import op
import sqlalchemy as sa

revision = "b7c8d9e0f1a2"
down_revision = "b1c2d3e4f5a6"
branch_labels = None
depends_on = None

SEED_TYPES = [
    {"code": "guia",          "name": "Guía",          "icon": "BookOpen",      "color": "#3B82F6", "sort_order": 1},
    {"code": "procedimiento", "name": "Procedimiento", "icon": "ListChecks",    "color": "#10B981", "sort_order": 2},
    {"code": "incidente",     "name": "Incidente",     "icon": "AlertTriangle", "color": "#EF4444", "sort_order": 3},
    {"code": "faq",           "name": "FAQ",           "icon": "HelpCircle",    "color": "#8B5CF6", "sort_order": 4},
]


def upgrade() -> None:
    op.create_table(
        "kb_document_types",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("code", sa.String(50), nullable=False, unique=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("icon", sa.String(50), nullable=False),
        sa.Column("color", sa.String(7), nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("sort_order", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.add_column(
        "kb_articles",
        sa.Column("document_type_id", sa.String(36), nullable=True),
    )
    op.create_foreign_key(
        "fk_kb_articles_document_type_id",
        "kb_articles",
        "kb_document_types",
        ["document_type_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_kb_articles_document_type_id",
        "kb_articles",
        ["document_type_id"],
    )

    conn = op.get_bind()
    for t in SEED_TYPES:
        existing = conn.execute(
            sa.text("SELECT 1 FROM kb_document_types WHERE code = :code LIMIT 1"),
            {"code": t["code"]},
        ).fetchone()
        if not existing:
            conn.execute(
                sa.text(
                    "INSERT INTO kb_document_types "
                    "(id, code, name, icon, color, sort_order) "
                    "VALUES (:id, :code, :name, :icon, :color, :sort_order)"
                ),
                {"id": str(uuid.uuid4()), **t},
            )


def downgrade() -> None:
    op.drop_index("ix_kb_articles_document_type_id", table_name="kb_articles")
    op.drop_constraint("fk_kb_articles_document_type_id", "kb_articles", type_="foreignkey")
    op.drop_column("kb_articles", "document_type_id")
    op.drop_table("kb_document_types")
