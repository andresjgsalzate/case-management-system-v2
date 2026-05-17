"""seed forensic permissions

Revision ID: 742f55a16be3
Revises: 0fa845d18d4f
Create Date: 2026-05-17 09:50:55.739450

Sub-spec 07 Task 3: 7 forensic actions distributed across the existing
Super Admin/Admin/Manager/Agent/Reporter roles. The spec uses SOC L1/L2/L3
+ Tenant Admin terminology; we apply the same pragmatic mapping established
by `seed_n8n_bridge_permissions` (538c6aad7c8f):

- Super Admin/Admin: all 7 (full forensic governance)
- Manager: read + launch_ro + launch_evidence + cancel_own + cancel_any
- Agent: read + launch_ro + cancel_own
- Reporter: read only
"""
from typing import Sequence, Union
import uuid

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '742f55a16be3'
down_revision: Union[str, None] = '0fa845d18d4f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


PERMS_BY_ROLE: dict[str, list[tuple[str, str]]] = {
    "Super Admin": [
        ("forensic", "read"),
        ("forensic", "launch_ro"),
        ("forensic", "launch_evidence"),
        ("forensic", "cancel_own"),
        ("forensic", "cancel_any"),
        ("forensic", "sync_catalog"),
        ("forensic", "manage_featured"),
    ],
    "Admin": [
        ("forensic", "read"),
        ("forensic", "launch_ro"),
        ("forensic", "launch_evidence"),
        ("forensic", "cancel_own"),
        ("forensic", "cancel_any"),
        ("forensic", "sync_catalog"),
        ("forensic", "manage_featured"),
    ],
    "Manager": [
        ("forensic", "read"),
        ("forensic", "launch_ro"),
        ("forensic", "launch_evidence"),
        ("forensic", "cancel_own"),
        ("forensic", "cancel_any"),
    ],
    "Agent": [
        ("forensic", "read"),
        ("forensic", "launch_ro"),
        ("forensic", "cancel_own"),
    ],
    "Reporter": [
        ("forensic", "read"),
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
    op.execute("DELETE FROM permissions WHERE module = 'forensic'")
