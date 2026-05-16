"""seed soc teams

Revision ID: f54597421e0e
Revises: 91d969b2c431
Create Date: 2026-05-15 13:36:54.623627

Sub-spec 02 Task 5: insert 17 SOC global teams per spec §4.1.

Plan referenced 'slug' for idempotency but TeamModel does not have a slug column,
so we use (tenant_id IS NULL, name) as the dedup key. Deterministic UUIDs derived
via uuid5(NAMESPACE_DNS, "soc-team:" + name) so repeated runs are stable.
"""
import uuid
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f54597421e0e'
down_revision: Union[str, None] = '91d969b2c431'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# (name, team_category, is_notification_only)
TEAMS: list[tuple[str, str, bool]] = [
    # operational — can be assigned to cases AND receive notifications
    ("Incidentes - SOC",      "operational",       False),
    ("Soporte IT",            "operational",       False),
    ("Customer Success",      "operational",       True),
    # technical_support — assigned to cases AND notified
    ("Infraestructura",       "technical_support", False),
    ("Bases de datos",        "technical_support", False),
    ("Aplicaciones",          "technical_support", False),
    ("Adm. Antivirus",        "technical_support", False),
    ("Adm. Correo",           "technical_support", False),
    ("Net&Sec",               "technical_support", False),
    ("Ethical Hacker",        "technical_support", False),
    # governance — typically notified only
    ("Segu Info. - Risk",     "governance",        False),
    ("Recursos Humanos",      "governance",        True),
    ("Datos Personales",      "governance",        True),
    # legal
    ("Legal",                 "legal",             True),
    # executive
    ("Director de Producto",  "executive",         True),
    ("Director Arquitectura", "executive",         True),
    ("Alta Dirección",        "executive",         True),
]

# Use a stable namespace UUID so deterministic uuid5() yields the same IDs
# across runs and environments.
_NAMESPACE = uuid.UUID("00000000-0000-5000-8000-000000000002")  # Sub-spec 02


def _team_id(name: str) -> str:
    return str(uuid.uuid5(_NAMESPACE, f"soc-team:{name}"))


def upgrade() -> None:
    conn = op.get_bind()
    for name, category, notif_only in TEAMS:
        existing = conn.execute(
            sa.text(
                "SELECT 1 FROM teams "
                "WHERE tenant_id IS NULL AND name = :name LIMIT 1"
            ),
            {"name": name},
        ).fetchone()
        if existing:
            continue
        conn.execute(
            sa.text(
                "INSERT INTO teams "
                "(id, tenant_id, name, team_category, is_notification_only, created_at) "
                "VALUES (:id, NULL, :name, :category, :notif_only, NOW())"
            ),
            {
                "id": _team_id(name), "name": name,
                "category": category, "notif_only": notif_only,
            },
        )


def downgrade() -> None:
    conn = op.get_bind()
    for name, _category, _notif_only in TEAMS:
        conn.execute(
            sa.text(
                "DELETE FROM teams "
                "WHERE tenant_id IS NULL AND id = :id"
            ),
            {"id": _team_id(name)},
        )
