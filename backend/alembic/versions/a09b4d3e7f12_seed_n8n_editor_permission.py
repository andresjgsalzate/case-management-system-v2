"""seed n8n_editor:access permission

Revision ID: a09b4d3e7f12
Revises: b7e2c9d5f81a
Create Date: 2026-05-22

Sub-spec 09 Task 3.1: a single permission gates the n8n iframe route.

Only the **Super Admin** role gets `n8n_editor:access` by default.
Other admins propose changes via the `workflow_change_requests`
tracker built in Phase 4 — that's the SOC2 compensating control
that lets us stay on n8n Community while we evaluate Enterprise.

Operators can grant the permission to other roles via the UI after
the migration runs (one INSERT into `permissions`).
"""
from typing import Sequence, Union
import uuid

from alembic import op
import sqlalchemy as sa


revision: str = "a09b4d3e7f12"
down_revision: Union[str, None] = "b7e2c9d5f81a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Deterministic UUIDs so re-runs against partially-seeded DBs don't
# duplicate rows. Different namespace from sub-spec 05 to keep seeds
# isolable (`downgrade` deletes by module name, not by UUID prefix).
NAMESPACE = uuid.UUID("99999999-aaaa-bbbb-cccc-ddddddddeeee")


def _id(role_id: str) -> str:
    return str(uuid.uuid5(NAMESPACE, f"perm:n8n_editor:access:{role_id}"))


PERMS_BY_ROLE: dict[str, list[tuple[str, str]]] = {
    "Super Admin": [("n8n_editor", "access")],
    # Admin / Manager / Agent / Reporter deliberately left out --
    # operator grants on demand. See docs/COMPLIANCE.md (Phase 4).
}


def upgrade() -> None:
    conn = op.get_bind()
    for role_name, perms in PERMS_BY_ROLE.items():
        role_row = conn.execute(
            sa.text(
                "SELECT id FROM roles "
                "WHERE name = :n AND tenant_id IS NULL LIMIT 1"
            ),
            {"n": role_name},
        ).fetchone()
        if not role_row:
            continue
        role_id = role_row[0]
        for module, action in perms:
            already = conn.execute(
                sa.text(
                    "SELECT 1 FROM permissions "
                    "WHERE role_id = :r AND module = :m AND action = :a LIMIT 1"
                ),
                {"r": role_id, "m": module, "a": action},
            ).fetchone()
            if already:
                continue
            conn.execute(
                sa.text(
                    "INSERT INTO permissions (id, role_id, module, action, scope) "
                    "VALUES (:id, :r, :m, :a, 'all')"
                ),
                {
                    "id": _id(role_id),
                    "r": role_id,
                    "m": module,
                    "a": action,
                },
            )


def downgrade() -> None:
    op.execute("DELETE FROM permissions WHERE module = 'n8n_editor'")
