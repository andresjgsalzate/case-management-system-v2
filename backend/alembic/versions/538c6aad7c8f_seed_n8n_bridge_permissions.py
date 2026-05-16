"""seed n8n_bridge permissions

Revision ID: 538c6aad7c8f
Revises: 5969cc00a74f
Create Date: 2026-05-16

Sub-spec 05 Task 2: 5 permissions across n8n_bridge + approvals modules.

Spec §3.5 defines a SOC L1/L2/L3 + Tenant/Platform Admin matrix; this repo
uses Super Admin/Admin/Manager/Agent/Reporter, so we apply the same
pragmatic mapping used in Plan 03 + 04 seeds:
- Super Admin/Admin: all 5
- Manager: read + trigger + cancel + approve (no per-tenant scoping yet)
- Agent: approvals:read + n8n_bridge:read_runs + trigger
- Reporter: approvals:read only
"""
from typing import Sequence, Union
import uuid

from alembic import op
import sqlalchemy as sa


revision: str = '538c6aad7c8f'
down_revision: Union[str, None] = '5969cc00a74f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


PERMS_BY_ROLE: dict[str, list[tuple[str, str]]] = {
    "Super Admin": [
        ("n8n_bridge", "trigger_workflow"),
        ("n8n_bridge", "read_runs"),
        ("n8n_bridge", "cancel_run"),
        ("approvals", "approve"),
        ("approvals", "read"),
    ],
    "Admin": [
        ("n8n_bridge", "trigger_workflow"),
        ("n8n_bridge", "read_runs"),
        ("n8n_bridge", "cancel_run"),
        ("approvals", "approve"),
        ("approvals", "read"),
    ],
    "Manager": [
        ("n8n_bridge", "trigger_workflow"),
        ("n8n_bridge", "read_runs"),
        ("n8n_bridge", "cancel_run"),
        ("approvals", "approve"),
        ("approvals", "read"),
    ],
    "Agent": [
        ("n8n_bridge", "trigger_workflow"),
        ("n8n_bridge", "read_runs"),
        ("approvals", "read"),
    ],
    "Reporter": [
        ("approvals", "read"),
    ],
}

NAMESPACE = uuid.UUID("22222222-3333-4444-5555-666666666666")


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
        "DELETE FROM permissions WHERE module IN ('n8n_bridge', 'approvals')"
    )
