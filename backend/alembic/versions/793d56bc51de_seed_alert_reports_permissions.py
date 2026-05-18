"""seed alert_reports permissions

Revision ID: 793d56bc51de
Revises: 10bc0f6f25b0
Create Date: 2026-05-17 21:03:35.791902

Sub-spec 08 Task 2: 6 alert_reports actions distributed across the existing
Super Admin/Admin/Manager/Agent/Reporter roles. The spec (§3.5) uses
SOC L1/L2/L3 + Tenant Admin + Platform Admin; we apply the same pragmatic
mapping used by Sub-spec 05 (`seed_n8n_bridge_permissions`) and Sub-spec 07
(`seed_forensic_permissions`):

- Super Admin: all 6 (Platform Admin equivalent — `["*"]` from spec)
- Admin: all 6 (Tenant Admin equivalent)
- Manager: read + generate + view_versions (SOC L3)
- Agent: read + generate (SOC L2)
- Reporter: read only (SOC L1)
"""
from typing import Sequence, Union
import uuid

from alembic import op
import sqlalchemy as sa


revision: str = '793d56bc51de'
down_revision: Union[str, None] = '10bc0f6f25b0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


PERMS_BY_ROLE: dict[str, list[tuple[str, str]]] = {
    "Super Admin": [
        ("alert_reports", "read"),
        ("alert_reports", "generate"),
        ("alert_reports", "delete"),
        ("alert_reports", "manage_templates"),
        ("alert_reports", "set_default"),
        ("alert_reports", "view_versions"),
    ],
    "Admin": [
        ("alert_reports", "read"),
        ("alert_reports", "generate"),
        ("alert_reports", "delete"),
        ("alert_reports", "manage_templates"),
        ("alert_reports", "set_default"),
        ("alert_reports", "view_versions"),
    ],
    "Manager": [
        ("alert_reports", "read"),
        ("alert_reports", "generate"),
        ("alert_reports", "view_versions"),
    ],
    "Agent": [
        ("alert_reports", "read"),
        ("alert_reports", "generate"),
    ],
    "Reporter": [
        ("alert_reports", "read"),
    ],
}

NAMESPACE = uuid.UUID("44444444-5555-6666-7777-888888888888")


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
    op.execute("DELETE FROM permissions WHERE module = 'alert_reports'")
