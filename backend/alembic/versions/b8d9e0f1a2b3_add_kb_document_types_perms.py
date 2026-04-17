"""add document_types permissions to roles

Revision ID: b8d9e0f1a2b3
Revises: b7c8d9e0f1a2
Create Date: 2026-04-16
"""
import uuid
from alembic import op
import sqlalchemy as sa

revision = "b8d9e0f1a2b3"
down_revision = "b7c8d9e0f1a2"
branch_labels = None
depends_on = None

# Perms granted to Admin role
ADMIN_PERMS = [
    ("document_types", "read",   "all"),
    ("document_types", "create", "all"),
    ("document_types", "update", "all"),
    ("document_types", "delete", "all"),
]

# Every other role only gets read
READ_ONLY_ROLES = ("Manager", "Agent", "Reporter")


def _grant(conn, role_id, module, action, scope):
    existing = conn.execute(
        sa.text(
            "SELECT 1 FROM permissions "
            "WHERE role_id = :role_id AND module = :module AND action = :action LIMIT 1"
        ),
        {"role_id": role_id, "module": module, "action": action},
    ).fetchone()
    if existing:
        return
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


def upgrade() -> None:
    conn = op.get_bind()

    admin_row = conn.execute(
        sa.text("SELECT id FROM roles WHERE name = 'Admin' AND tenant_id IS NULL LIMIT 1")
    ).fetchone()
    if admin_row:
        for module, action, scope in ADMIN_PERMS:
            _grant(conn, admin_row[0], module, action, scope)

    for role_name in READ_ONLY_ROLES:
        row = conn.execute(
            sa.text("SELECT id FROM roles WHERE name = :name AND tenant_id IS NULL LIMIT 1"),
            {"name": role_name},
        ).fetchone()
        if row:
            _grant(conn, row[0], "document_types", "read", "all")


def downgrade() -> None:
    conn = op.get_bind()

    admin_row = conn.execute(
        sa.text("SELECT id FROM roles WHERE name = 'Admin' AND tenant_id IS NULL LIMIT 1")
    ).fetchone()
    if admin_row:
        for module, action, _ in ADMIN_PERMS:
            conn.execute(
                sa.text(
                    "DELETE FROM permissions "
                    "WHERE role_id = :role_id AND module = :module AND action = :action"
                ),
                {"role_id": admin_row[0], "module": module, "action": action},
            )

    for role_name in READ_ONLY_ROLES:
        row = conn.execute(
            sa.text("SELECT id FROM roles WHERE name = :name AND tenant_id IS NULL LIMIT 1"),
            {"name": role_name},
        ).fetchone()
        if row:
            conn.execute(
                sa.text(
                    "DELETE FROM permissions "
                    "WHERE role_id = :role_id AND module = 'document_types' AND action = 'read'"
                ),
                {"role_id": row[0]},
            )
