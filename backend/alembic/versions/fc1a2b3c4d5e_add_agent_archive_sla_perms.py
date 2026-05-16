"""add archive and sla/read permissions to Agent role

Revision ID: fc1a2b3c4d5e
Revises: eb25e09451ce
Create Date: 2026-04-15
"""
import uuid
from alembic import op
import sqlalchemy as sa

revision = "fc1a2b3c4d5e"
down_revision = "eb25e09451ce"
branch_labels = None
depends_on = None

# Permissions to add to the Agent role
NEW_AGENT_PERMS = [
    ("cases",  "archive", "own"),  # agents can archive closed cases they worked on
    ("sla",    "read",    "own"),  # agents need to see SLA status on their cases
]


def upgrade() -> None:
    conn = op.get_bind()

    agent_row = conn.execute(
        sa.text("SELECT id FROM roles WHERE name = 'Agent' AND tenant_id IS NULL LIMIT 1")
    ).fetchone()

    if not agent_row:
        return  # role not seeded yet; seed.py will handle it

    role_id = agent_row[0]

    for module, action, scope in NEW_AGENT_PERMS:
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

    agent_row = conn.execute(
        sa.text("SELECT id FROM roles WHERE name = 'Agent' AND tenant_id IS NULL LIMIT 1")
    ).fetchone()

    if not agent_row:
        return

    role_id = agent_row[0]

    for module, action, _ in NEW_AGENT_PERMS:
        conn.execute(
            sa.text(
                "DELETE FROM permissions "
                "WHERE role_id = :role_id AND module = :module AND action = :action"
            ),
            {"role_id": role_id, "module": module, "action": action},
        )
