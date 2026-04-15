"""forensic audit columns

Revision ID: f9a0b1c2d3e4
Revises: e7f8a9b0c1d2
Create Date: 2026-04-15
"""
from alembic import op
import sqlalchemy as sa

revision = "f9a0b1c2d3e4"
down_revision = "e7f8a9b0c1d2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("audit_logs", sa.Column("correlation_id", sa.String(36), nullable=True))
    op.add_column("audit_logs", sa.Column("before_snapshot", sa.JSON(), nullable=True))
    op.add_column("audit_logs", sa.Column("user_agent", sa.String(500), nullable=True))
    op.add_column("audit_logs", sa.Column("request_path", sa.String(200), nullable=True))

    op.create_index("ix_audit_logs_correlation_id", "audit_logs", ["correlation_id"])

    op.execute("""
        CREATE OR REPLACE FUNCTION prevent_audit_modification()
        RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'audit_logs records are immutable';
        END;
        $$ LANGUAGE plpgsql;
    """)

    op.execute("""
        CREATE TRIGGER audit_logs_immutable
        BEFORE UPDATE OR DELETE ON audit_logs
        FOR EACH ROW EXECUTE FUNCTION prevent_audit_modification();
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS audit_logs_immutable ON audit_logs;")
    op.execute("DROP FUNCTION IF EXISTS prevent_audit_modification();")
    op.drop_index("ix_audit_logs_correlation_id", table_name="audit_logs")
    op.drop_column("audit_logs", "request_path")
    op.drop_column("audit_logs", "user_agent")
    op.drop_column("audit_logs", "before_snapshot")
    op.drop_column("audit_logs", "correlation_id")
