"""seed n8n_workflows permissions

Revision ID: d4a8b2c1e6f5
Revises: c8f3e7a4d9b1
Create Date: 2026-05-19

4 permissions on the n8n_workflows module (read/create/update/delete).
Trigger-time permission lives on n8n_bridge:trigger_workflow (existing).

Role mapping mirrors the operator-tier pattern from 538c6aad7c8f:
- Super Admin / Admin / Manager: full CRUD on catalog
- Agent: read only (sees catalog when triggering)
- Reporter: no access
"""
from typing import Sequence, Union
import uuid

from alembic import op
import sqlalchemy as sa


revision: str = 'd4a8b2c1e6f5'
down_revision: Union[str, None] = 'c8f3e7a4d9b1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


PERMS_BY_ROLE: dict[str, list[tuple[str, str]]] = {
    "Super Admin": [
        ("n8n_workflows", "read"),
        ("n8n_workflows", "create"),
        ("n8n_workflows", "update"),
        ("n8n_workflows", "delete"),
    ],
    "Admin": [
        ("n8n_workflows", "read"),
        ("n8n_workflows", "create"),
        ("n8n_workflows", "update"),
        ("n8n_workflows", "delete"),
    ],
    "Manager": [
        ("n8n_workflows", "read"),
        ("n8n_workflows", "create"),
        ("n8n_workflows", "update"),
        ("n8n_workflows", "delete"),
    ],
    "Agent": [
        ("n8n_workflows", "read"),
    ],
}

NAMESPACE = uuid.UUID("33333333-4444-5555-6666-777777777777")


def _id(kind: str, key: str) -> str:
    return str(uuid.uuid5(NAMESPACE, f"{kind}:{key}"))


def upgrade() -> None:
    conn = op.get_bind()
    for role_name, perms in PERMS_BY_ROLE.items():
        role_row = conn.execute(sa.text(
            "SELECT id FROM roles WHERE name = :n AND tenant_id IS NULL LIMIT 1"
        ), {"n": role_name}).fetchone()
        if not role_row:
            continue
        role_id = role_row[0]
        for module, action in perms:
            existing = conn.execute(sa.text(
                "SELECT 1 FROM permissions "
                "WHERE role_id = :r AND module = :m AND action = :a LIMIT 1"
            ), {"r": role_id, "m": module, "a": action}).fetchone()
            if existing:
                continue
            conn.execute(sa.text(
                "INSERT INTO permissions (id, role_id, module, action, scope) "
                "VALUES (:id, :r, :m, :a, 'all')"
            ), {
                "id": _id("perm", f"{role_id}:{module}:{action}"),
                "r": role_id, "m": module, "a": action,
            })


def downgrade() -> None:
    op.execute(
        "DELETE FROM permissions WHERE module = 'n8n_workflows'"
    )
