"""seed operational_center permissions

Revision ID: 5308b8cc935f
Revises: f83d15caabf7
Create Date: 2026-05-16

Sub-spec 06 Task 2: 4 permissions across 3 modules.

Spec §3.2 defines a SOC L1/L2/L3 + Tenant/Platform Admin matrix; this repo
uses Super Admin/Admin/Manager/Agent/Reporter, pragmatic mapping:
- Super Admin / Admin / Manager: full (4 permissions)
- Agent: read dashboard + integration health
- Reporter: read dashboard only
"""
from typing import Sequence, Union
import uuid

from alembic import op
import sqlalchemy as sa


revision: str = '5308b8cc935f'
down_revision: Union[str, None] = 'f83d15caabf7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


PERMS_BY_ROLE: dict[str, list[tuple[str, str]]] = {
    "Super Admin": [
        ("dashboard_soc", "read"),
        ("audit_explorer", "read"),
        ("audit_explorer", "export"),
        ("integration_health", "read"),
    ],
    "Admin": [
        ("dashboard_soc", "read"),
        ("audit_explorer", "read"),
        ("audit_explorer", "export"),
        ("integration_health", "read"),
    ],
    "Manager": [
        ("dashboard_soc", "read"),
        ("audit_explorer", "read"),
        ("audit_explorer", "export"),
        ("integration_health", "read"),
    ],
    "Agent": [
        ("dashboard_soc", "read"),
        ("integration_health", "read"),
    ],
    "Reporter": [
        ("dashboard_soc", "read"),
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
        "DELETE FROM permissions WHERE module IN "
        "('dashboard_soc', 'audit_explorer', 'integration_health')"
    )
