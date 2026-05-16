"""seed security_taxonomies permissions

Revision ID: 91d969b2c431
Revises: 7c155524a515
Create Date: 2026-05-15 09:13:39.800699

Sub-spec 02 Task 4: insert 8 security_taxonomies permissions and assign them
to existing global roles per a pragmatic mapping (the spec mentions SOC L1/L2/L3
+ Tenant Admin + Platform Admin which don't exist yet in this repo; we map to
Reporter/Agent/Manager/Admin/Super Admin respectively).

If a future spec introduces SOC-specific role names, a follow-up migration can
re-assign these permissions.
"""
import uuid
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '91d969b2c431'
down_revision: Union[str, None] = '7c155524a515'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# (role_name, action, scope) — module is always 'security_taxonomies'
ROLE_PERMS: list[tuple[str, str, str]] = [
    # Super Admin (Platform Admin equivalent) — full access including manage_global
    ("Super Admin", "read",            "all"),
    ("Super Admin", "create",          "all"),
    ("Super Admin", "update",          "all"),
    ("Super Admin", "delete",          "all"),
    ("Super Admin", "manage_global",   "all"),
    ("Super Admin", "read_audit_log",  "all"),
    ("Super Admin", "export",          "all"),
    ("Super Admin", "import",          "all"),
    # Admin (Tenant Admin equivalent) — everything except manage_global
    ("Admin",       "read",            "all"),
    ("Admin",       "create",          "all"),
    ("Admin",       "update",          "all"),
    ("Admin",       "delete",          "all"),
    ("Admin",       "read_audit_log",  "all"),
    ("Admin",       "export",          "all"),
    ("Admin",       "import",          "all"),
    # Manager (SOC L3 equivalent) — read/create/update + audit + export
    ("Manager",     "read",            "all"),
    ("Manager",     "create",          "all"),
    ("Manager",     "update",          "all"),
    ("Manager",     "read_audit_log",  "all"),
    ("Manager",     "export",          "all"),
    # Agent (SOC L2 equivalent) — read + audit
    ("Agent",       "read",            "all"),
    ("Agent",       "read_audit_log",  "all"),
    # Reporter (SOC L1 equivalent) — read only
    ("Reporter",    "read",            "all"),
]

MODULE = "security_taxonomies"


def upgrade() -> None:
    conn = op.get_bind()
    for role_name, action, scope in ROLE_PERMS:
        row = conn.execute(
            sa.text(
                "SELECT id FROM roles WHERE name = :name AND tenant_id IS NULL LIMIT 1"
            ),
            {"name": role_name},
        ).fetchone()
        if not row:
            continue
        role_id = row[0]
        existing = conn.execute(
            sa.text(
                "SELECT 1 FROM permissions "
                "WHERE role_id = :role_id AND module = :module AND action = :action LIMIT 1"
            ),
            {"role_id": role_id, "module": MODULE, "action": action},
        ).fetchone()
        if not existing:
            conn.execute(
                sa.text(
                    "INSERT INTO permissions (id, role_id, module, action, scope) "
                    "VALUES (:id, :role_id, :module, :action, :scope)"
                ),
                {
                    "id": str(uuid.uuid4()), "role_id": role_id,
                    "module": MODULE, "action": action, "scope": scope,
                },
            )


def downgrade() -> None:
    conn = op.get_bind()
    for role_name, action, _scope in ROLE_PERMS:
        row = conn.execute(
            sa.text(
                "SELECT id FROM roles WHERE name = :name AND tenant_id IS NULL LIMIT 1"
            ),
            {"name": role_name},
        ).fetchone()
        if not row:
            continue
        conn.execute(
            sa.text(
                "DELETE FROM permissions "
                "WHERE role_id = :role_id AND module = :module AND action = :action"
            ),
            {"role_id": row[0], "module": MODULE, "action": action},
        )
