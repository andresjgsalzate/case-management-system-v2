"""add knowledge_base.create permission to Agent and Manager roles

Revision ID: b1c2d3e4f5a6
Revises: a2b3c4d5e6f7
Create Date: 2026-04-16
"""
import uuid
from alembic import op
import sqlalchemy as sa

revision = "b1c2d3e4f5a6"
down_revision = "a2b3c4d5e6f7"
branch_labels = None
depends_on = None

NEW_PERMS = [
    ("Agent",   "knowledge_base", "create", "all"),
    ("Manager", "knowledge_base", "create", "all"),
]


def upgrade() -> None:
    conn = op.get_bind()
    for role_name, module, action, scope in NEW_PERMS:
        row = conn.execute(
            sa.text("SELECT id FROM roles WHERE name = :name AND tenant_id IS NULL LIMIT 1"),
            {"name": role_name},
        ).fetchone()
        if not row:
            continue
        role_id = row[0]
        existing = conn.execute(
            sa.text(
                "SELECT 1 FROM permissions "
                "WHERE role_id = :role_id AND module = :module AND action = :action LIMIT 1"
            ),
            {"role_id": role_id, "module": module, "action": action},
        ).fetchone()
        if not existing:
            conn.execute(
                sa.text(
                    "INSERT INTO permissions (id, role_id, module, action, scope) "
                    "VALUES (:id, :role_id, :module, :action, :scope)"
                ),
                {"id": str(uuid.uuid4()), "role_id": role_id,
                 "module": module, "action": action, "scope": scope},
            )


def downgrade() -> None:
    conn = op.get_bind()
    for role_name, module, action, _scope in NEW_PERMS:
        row = conn.execute(
            sa.text("SELECT id FROM roles WHERE name = :name AND tenant_id IS NULL LIMIT 1"),
            {"name": role_name},
        ).fetchone()
        if not row:
            continue
        conn.execute(
            sa.text(
                "DELETE FROM permissions "
                "WHERE role_id = :role_id AND module = :module AND action = :action"
            ),
            {"role_id": row[0], "module": module, "action": action},
        )
