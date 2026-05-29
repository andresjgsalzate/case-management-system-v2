"""seed enrichment and wazuh_query permissions

Revision ID: a1f2e3d4c5b6
Revises: b295b29f3978
Create Date: 2026-05-28

Permisos para los módulos enrichment (VT+OTX) y wazuh_query (syscheck outbound).
Roles receptores: SOC L1, SOC L2, SOC Admin (creados en scripts/seed.py).
"""
from typing import Sequence, Union
import uuid

from alembic import op
import sqlalchemy as sa


revision: str = 'a1f2e3d4c5b6'
down_revision: Union[str, None] = 'b295b29f3978'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

NAMESPACE = uuid.UUID("a1b2c3d4-e5f6-7890-abcd-ef1234567890")


def _id(key: str) -> str:
    return str(uuid.uuid5(NAMESPACE, key))


# (module, action, scope, roles_that_get_it)
PERMS: list[tuple[str, str, str, list[str]]] = [
    ("enrichment", "query",         "all", ["SOC L1", "SOC L2", "SOC Admin"]),
    ("enrichment", "configure",     "all", ["SOC Admin"]),
    ("wazuh",      "query_syscheck","all", ["SOC L1", "SOC L2", "SOC Admin"]),
]


def upgrade() -> None:
    conn = op.get_bind()
    for module, action, scope, role_names in PERMS:
        for role_name in role_names:
            role_row = conn.execute(sa.text(
                "SELECT id FROM roles WHERE name = :n AND tenant_id IS NULL LIMIT 1"
            ), {"n": role_name}).fetchone()
            if not role_row:
                continue
            role_id = role_row[0]
            existing = conn.execute(sa.text(
                "SELECT 1 FROM permissions "
                "WHERE role_id = :r AND module = :m AND action = :a LIMIT 1"
            ), {"r": role_id, "m": module, "a": action}).fetchone()
            if existing:
                continue
            conn.execute(sa.text(
                "INSERT INTO permissions (id, role_id, module, action, scope) "
                "VALUES (:id, :r, :m, :a, :s)"
            ), {
                "id": _id(f"{role_id}:{module}:{action}"),
                "r": role_id, "m": module, "a": action, "s": scope,
            })


def downgrade() -> None:
    op.execute(
        "DELETE FROM permissions WHERE module IN ('enrichment', 'wazuh')"
    )
