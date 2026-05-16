"""add attachments and extra permissions to Reporter role

Revision ID: a2b3c4d5e6f7
Revises: fc1a2b3c4d5e
Create Date: 2026-04-15
"""
import uuid
from alembic import op
import sqlalchemy as sa

revision = "a2b3c4d5e6f7"
down_revision = "fc1a2b3c4d5e"
branch_labels = None
depends_on = None

# Permissions missing from the initial Reporter migration
NEW_REPORTER_PERMS = [
    ("attachments",    "read",   "team"),
    ("attachments",    "create", "own"),
    ("attachments",    "delete", "own"),
    ("time_entries",   "read",   "own"),
    ("knowledge_base", "read",   "all"),
    ("search",         "read",   "all"),
    ("classification", "read",   "own"),
    ("classification", "create", "own"),
]


def upgrade() -> None:
    conn = op.get_bind()

    reporter_row = conn.execute(
        sa.text("SELECT id FROM roles WHERE name = 'Reporter' AND tenant_id IS NULL LIMIT 1")
    ).fetchone()

    if not reporter_row:
        return  # role not seeded yet; seed.py will handle it

    role_id = reporter_row[0]

    for module, action, scope in NEW_REPORTER_PERMS:
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

    reporter_row = conn.execute(
        sa.text("SELECT id FROM roles WHERE name = 'Reporter' AND tenant_id IS NULL LIMIT 1")
    ).fetchone()

    if not reporter_row:
        return

    role_id = reporter_row[0]

    for module, action, _ in NEW_REPORTER_PERMS:
        conn.execute(
            sa.text(
                "DELETE FROM permissions "
                "WHERE role_id = :role_id AND module = :module AND action = :action"
            ),
            {"role_id": role_id, "module": module, "action": action},
        )
