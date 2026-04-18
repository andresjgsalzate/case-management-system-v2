"""add kb_article_cases table

Revision ID: a3b4c5d6e7f8
Revises: 1f35f05d8d94
Create Date: 2026-04-17
"""
from alembic import op
import sqlalchemy as sa

revision = "a3b4c5d6e7f8"
down_revision = "1f35f05d8d94"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "kb_article_cases",
        sa.Column("article_id", sa.String(36), nullable=False),
        sa.Column("case_id", sa.String(36), nullable=False),
        sa.Column("linked_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("linked_by_id", sa.String(36), nullable=False),
        sa.ForeignKeyConstraint(["article_id"], ["kb_articles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["linked_by_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("article_id", "case_id"),
    )
    op.create_index(
        "ix_kb_article_cases_case_id", "kb_article_cases", ["case_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_kb_article_cases_case_id", table_name="kb_article_cases")
    op.drop_table("kb_article_cases")
