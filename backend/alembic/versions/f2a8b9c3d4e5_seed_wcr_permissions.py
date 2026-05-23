"""seed workflow_change_requests permissions

Revision ID: f2a8b9c3d4e5
Revises: e7d9a1c45b2f
Create Date: 2026-05-22

Sub-spec 09 §3.9 Task 4.4: three permissions for the WCR tracker.

| Permission                          | Roles                |
|-------------------------------------|----------------------|
| workflow_change_requests:create     | Admin, Manager       |
| workflow_change_requests:read       | Admin, Manager       |
| workflow_change_requests:review     | Super Admin (== holder of n8n_editor:access in v1) |

Operators can extend `:review` to more users by manually inserting
rows into `permissions` -- the use case checks the role's permission,
not the user's identity.
"""
from typing import Sequence, Union
import uuid

from alembic import op
import sqlalchemy as sa


revision: str = "f2a8b9c3d4e5"
down_revision: Union[str, None] = "e7d9a1c45b2f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


NAMESPACE = uuid.UUID("33333333-7777-8888-9999-aaaaaaaaaaaa")


def _id(role_id: str, action: str) -> str:
    return str(uuid.uuid5(NAMESPACE, f"perm:wcr:{action}:{role_id}"))


PERMS_BY_ROLE: dict[str, list[str]] = {
    "Super Admin": ["create", "read", "review"],
    "Admin":       ["create", "read"],
    "Manager":     ["create", "read"],
}


def upgrade() -> None:
    conn = op.get_bind()
    for role_name, actions in PERMS_BY_ROLE.items():
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
        for action in actions:
            already = conn.execute(
                sa.text(
                    "SELECT 1 FROM permissions "
                    "WHERE role_id = :r AND module = :m AND action = :a LIMIT 1"
                ),
                {"r": role_id, "m": "workflow_change_requests", "a": action},
            ).fetchone()
            if already:
                continue
            conn.execute(
                sa.text(
                    "INSERT INTO permissions (id, role_id, module, action, scope) "
                    "VALUES (:id, :r, :m, :a, 'all')"
                ),
                {
                    "id": _id(role_id, action),
                    "r": role_id,
                    "m": "workflow_change_requests",
                    "a": action,
                },
            )


def downgrade() -> None:
    op.execute(
        "DELETE FROM permissions WHERE module = 'workflow_change_requests'"
    )
