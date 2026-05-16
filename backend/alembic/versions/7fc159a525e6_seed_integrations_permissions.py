"""seed integrations permissions

Revision ID: 7fc159a525e6
Revises: 272dad9e3794
Create Date: 2026-05-16

Sub-spec 04 Task 14: 4 permissions assigned to existing roles.

Spec §5.3 defines a SOC L1/L2/L3 + Tenant/Platform Admin matrix; this repo
uses Super Admin / Admin / Manager / Agent / Reporter, so we apply a
pragmatic mapping that preserves the spec's intent:
- Super Admin / Admin / Manager: full integrations capabilities
- Agent / Reporter: read_events only (visibility into the inbound log)
"""
from typing import Sequence, Union
import uuid

from alembic import op
import sqlalchemy as sa


revision: str = '7fc159a525e6'
down_revision: Union[str, None] = '272dad9e3794'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


PERMS_BY_ROLE: dict[str, list[str]] = {
    "Super Admin": ["read", "manage", "read_events", "replay_events"],
    "Admin":       ["read", "manage", "read_events", "replay_events"],
    "Manager":     ["read",           "read_events", "replay_events"],
    "Agent":       [                  "read_events"],
    "Reporter":    [                  "read_events"],
}

MODULE = "integrations"
NAMESPACE = uuid.UUID("11111111-2222-3333-4444-555555555555")


def _id(kind: str, key: str) -> str:
    return str(uuid.uuid5(NAMESPACE, f"{kind}:{key}"))


def upgrade() -> None:
    conn = op.get_bind()
    for role_name, actions in PERMS_BY_ROLE.items():
        role_row = conn.execute(sa.text(
            "SELECT id FROM roles WHERE name = :n AND tenant_id IS NULL LIMIT 1"
        ), {"n": role_name}).fetchone()
        if not role_row:
            continue
        role_id = role_row[0]
        for action in actions:
            existing = conn.execute(sa.text(
                "SELECT 1 FROM permissions "
                "WHERE role_id = :r AND module = :m AND action = :a LIMIT 1"
            ), {"r": role_id, "m": MODULE, "a": action}).fetchone()
            if existing:
                continue
            conn.execute(sa.text(
                "INSERT INTO permissions (id, role_id, module, action, scope) "
                "VALUES (:id, :r, :m, :a, 'all')"
            ), {
                "id": _id("perm", f"{role_id}:{action}"),
                "r": role_id, "m": MODULE, "a": action,
            })


def downgrade() -> None:
    op.execute("DELETE FROM permissions WHERE module = 'integrations'")
