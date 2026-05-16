"""add Reporter role

Revision ID: eb25e09451ce
Revises: 067bf148971a
Create Date: 2026-04-15
"""
import uuid
from alembic import op
import sqlalchemy as sa
from datetime import datetime, timezone

revision = "eb25e09451ce"
down_revision = "067bf148971a"
branch_labels = None
depends_on = None

REPORTER_PERMISSIONS = [
    ("cases",         "create",     "own"),
    ("cases",         "read",       "own"),
    ("cases",         "transition", "own"),
    ("notifications", "read",       "own"),
]


def upgrade() -> None:
    conn = op.get_bind()

    # Skip if role already exists
    existing = conn.execute(
        sa.text("SELECT id FROM roles WHERE name = 'Reporter' AND tenant_id IS NULL LIMIT 1")
    ).fetchone()
    if existing:
        return

    role_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)

    conn.execute(
        sa.text(
            "INSERT INTO roles (id, tenant_id, name, description, is_global, created_at) "
            "VALUES (:id, NULL, 'Reporter', "
            "'Usuario que reporta y hace seguimiento de sus propios casos', "
            "false, :created_at)"
        ),
        {"id": role_id, "created_at": now},
    )

    for module, action, scope in REPORTER_PERMISSIONS:
        conn.execute(
            sa.text(
                "INSERT INTO permissions (id, role_id, module, action, scope) "
                "VALUES (:id, :role_id, :module, :action, :scope)"
            ),
            {
                "id": str(uuid.uuid4()),
                "role_id": role_id,
                "module": module,
                "action": action,
                "scope": scope,
            },
        )


def downgrade() -> None:
    conn = op.get_bind()
    result = conn.execute(
        sa.text("SELECT id FROM roles WHERE name = 'Reporter' AND tenant_id IS NULL LIMIT 1")
    ).fetchone()
    if result:
        conn.execute(
            sa.text("DELETE FROM permissions WHERE role_id = :rid"),
            {"rid": result[0]},
        )
        conn.execute(
            sa.text("DELETE FROM roles WHERE id = :rid"),
            {"rid": result[0]},
        )
