"""kb_articles: visibility + pending_visibility

Revision ID: a5b6c7d8e9f0
Revises: f4a5b6c7d8e9
Create Date: 2026-04-25

Añade el concepto de visibilidad por artículo:
- visibility: el valor activo (private | team | public). Default 'private'.
- pending_visibility: cambio pendiente de aprobación (cuando se solicita
  pasar a 'public', queda aquí hasta que un aprobador lo confirme).
"""
from alembic import op
import sqlalchemy as sa


revision = "a5b6c7d8e9f0"
down_revision = "f4a5b6c7d8e9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "kb_articles",
        sa.Column(
            "visibility",
            sa.String(20),
            nullable=False,
            server_default="private",
        ),
    )
    op.add_column(
        "kb_articles",
        sa.Column(
            "pending_visibility",
            sa.String(20),
            nullable=True,
        ),
    )
    op.create_check_constraint(
        "kb_articles_visibility_valid",
        "kb_articles",
        "visibility IN ('private','team','public')",
    )
    op.create_check_constraint(
        "kb_articles_pending_visibility_valid",
        "kb_articles",
        "pending_visibility IS NULL OR pending_visibility IN ('private','team','public')",
    )
    op.create_index("idx_kb_articles_visibility", "kb_articles", ["visibility"])


def downgrade() -> None:
    op.drop_index("idx_kb_articles_visibility", table_name="kb_articles")
    op.drop_constraint("kb_articles_pending_visibility_valid", "kb_articles", type_="check")
    op.drop_constraint("kb_articles_visibility_valid", "kb_articles", type_="check")
    op.drop_column("kb_articles", "pending_visibility")
    op.drop_column("kb_articles", "visibility")
