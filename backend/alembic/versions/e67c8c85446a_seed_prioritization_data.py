"""seed prioritization data

Revision ID: e67c8c85446a
Revises: 4f26d63dfe1b
Create Date: 2026-05-15 22:01:34.300069

Sub-spec 03 Task 3: bulk seed of prioritization config.

Inserts:
- 6 permissions × role assignments (Super Admin / Admin / Manager / Agent / Reporter)
- 6 global criteria (severity, impact, asset_criticality, data_sensitivity,
  user_visibility, repetition_count)
- 5 scales per criterion (Mínimo/Bajo/Medio/Alto/Crítico = 1-5) = 30 rows
- 3 global formulas v1 with criterion weights + 4 thresholds each:
    * soc-default        (severity 0.5, impact 0.3, asset_criticality 0.2)
    * compliance-focused (data_sensitivity 0.4, severity 0.3, impact 0.3)
    * user-impact-focused (user_visibility 0.4, severity 0.3, impact 0.3)

Thresholds reference case_priorities by name (existing seed has names in
Spanish: Baja, Media, Alta, Critica). Mapping: low=Baja, medium=Media,
high=Alta, critical=Critica.

Deterministic UUIDs via uuid5(NAMESPACE_SOC03, "<kind>:<key>") so reruns
are idempotent.
"""
import uuid
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e67c8c85446a'
down_revision: Union[str, None] = '4f26d63dfe1b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_NAMESPACE = uuid.UUID("00000000-0000-5000-8000-000000000003")


def _id(kind: str, key: str) -> str:
    return str(uuid.uuid5(_NAMESPACE, f"{kind}:{key}"))


# ── Permissions ─────────────────────────────────────────────────────────

PERMS_BY_ROLE: dict[str, list[str]] = {
    "Super Admin": [
        "read", "manage_criteria", "manage_formulas",
        "manage_global", "recalculate", "read_calculations",
    ],
    "Admin": [
        "read", "manage_criteria", "manage_formulas",
        "recalculate", "read_calculations",
    ],
    "Manager": [
        "read", "manage_criteria", "manage_formulas",
        "recalculate", "read_calculations",
    ],
    "Agent": ["read", "recalculate", "read_calculations"],
    "Reporter": ["read_calculations"],
}


# ── Criteria ────────────────────────────────────────────────────────────

# (code, name, description, data_source, source_field_key, missing_data_strategy, default_value, sort_order)
CRITERIA: list[tuple[str, str, str, str, str | None, str, int | None, int]] = [
    ("severity", "Severidad de la alerta",
     "Severidad técnica reportada por la fuente de detección",
     "taxonomy_field", "default_severity_value", "use_default", 3, 10),
    ("impact", "Impacto potencial",
     "Impacto estimado en el negocio si la amenaza se materializa",
     "case_custom_value", "impact", "use_default", 3, 20),
    ("asset_criticality", "Criticidad del activo afectado",
     "Importancia del activo según el inventario de aplicaciones",
     "asset_field", "criticality", "skip", None, 30),
    ("data_sensitivity", "Sensibilidad de la información (TLP)",
     "Nivel TLP de la información involucrada",
     "taxonomy_field", "tlp_default", "use_default", 3, 40),
    ("user_visibility", "Cantidad de usuarios afectados",
     "Número estimado de usuarios impactados",
     "case_custom_value", "affected_users_estimate", "skip", None, 50),
    ("repetition_count", "Frecuencia (repetición)",
     "Cuántas veces se ha visto un evento similar recientemente",
     "derived", "repetition_count_handler", "use_default", 1, 60),
]

# Standard 5-point scale applied to every criterion
SCALES = [
    ("Mínimo",  1, "#94a3b8"),
    ("Bajo",    2, "#22c55e"),
    ("Medio",   3, "#f59e0b"),
    ("Alto",    4, "#f97316"),
    ("Crítico", 5, "#ef4444"),
]


# ── Formulas ────────────────────────────────────────────────────────────

# (logical_key, name, description, weights, thresholds)
# weights: dict[criterion_code → Decimal]
# thresholds: list[(min, max, priority_name)] — priority_name maps to case_priorities.name
FORMULAS = [
    {
        "logical_key": "soc-default",
        "name": "SOC Default Formula 2026",
        "description": "Fórmula balanceada para operación SOC general",
        "weights": {"severity": 0.50, "impact": 0.30, "asset_criticality": 0.20},
        "thresholds": [
            (0.00, 2.49, "Baja"),
            (2.50, 3.49, "Media"),
            (3.50, 4.49, "Alta"),
            (4.50, 5.00, "Critica"),
        ],
    },
    {
        "logical_key": "compliance-focused",
        "name": "Compliance-Focused Formula",
        "description": "Énfasis en sensibilidad de información (PCI, GDPR, etc.)",
        "weights": {"data_sensitivity": 0.40, "severity": 0.30, "impact": 0.30},
        "thresholds": [
            (0.00, 1.99, "Baja"),
            (2.00, 2.99, "Media"),
            (3.00, 3.99, "Alta"),
            (4.00, 5.00, "Critica"),
        ],
    },
    {
        "logical_key": "user-impact-focused",
        "name": "User Impact Formula",
        "description": "Énfasis en cantidad de usuarios afectados",
        "weights": {"user_visibility": 0.40, "severity": 0.30, "impact": 0.30},
        "thresholds": [
            (0.00, 2.49, "Baja"),
            (2.50, 3.49, "Media"),
            (3.50, 4.49, "Alta"),
            (4.50, 5.00, "Critica"),
        ],
    },
]

MODULE = "prioritization"


def upgrade() -> None:
    conn = op.get_bind()

    # 1. Permissions
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

    # 2. Criteria
    for code, name, desc, data_source, src_key, missing, default_v, sort_order in CRITERIA:
        existing = conn.execute(sa.text(
            "SELECT 1 FROM prioritization_criteria "
            "WHERE tenant_id IS NULL AND code = :c LIMIT 1"
        ), {"c": code}).fetchone()
        if existing:
            continue
        conn.execute(sa.text(
            "INSERT INTO prioritization_criteria "
            "(id, tenant_id, code, name, description, data_source, source_field_key, "
            " missing_data_strategy, default_value, is_active, sort_order, "
            " created_at, updated_at) "
            "VALUES (:id, NULL, :code, :name, :desc, :ds, :sk, :ms, :dv, "
            "        true, :so, NOW(), NOW())"
        ), {
            "id": _id("criterion", code), "code": code, "name": name,
            "desc": desc, "ds": data_source, "sk": src_key,
            "ms": missing, "dv": default_v, "so": sort_order,
        })

    # 3. Scales (5 per criterion = 30 total)
    for code, *_ in CRITERIA:
        crit_id = _id("criterion", code)
        for label, numeric, color in SCALES:
            existing = conn.execute(sa.text(
                "SELECT 1 FROM prioritization_scales "
                "WHERE criterion_id = :cid AND numeric_value = :n LIMIT 1"
            ), {"cid": crit_id, "n": numeric}).fetchone()
            if existing:
                continue
            conn.execute(sa.text(
                "INSERT INTO prioritization_scales "
                "(id, criterion_id, label, numeric_value, color, sort_order) "
                "VALUES (:id, :cid, :label, :n, :color, :so)"
            ), {
                "id": _id("scale", f"{code}:{numeric}"),
                "cid": crit_id, "label": label, "n": numeric,
                "color": color, "so": numeric,
            })

    # 4. Formulas + criteria + thresholds
    # Resolve creator user
    user_row = conn.execute(sa.text(
        "SELECT u.id FROM users u JOIN roles r ON r.id = u.role_id "
        "WHERE r.name IN ('Super Admin', 'Admin') AND r.tenant_id IS NULL "
        "ORDER BY u.created_at ASC LIMIT 1"
    )).fetchone()
    if not user_row:
        raise RuntimeError(
            "No Super Admin / Admin user found — cannot seed formulas"
        )
    user_id = user_row[0]

    # Resolve case_priorities by name
    pri_rows = conn.execute(sa.text(
        "SELECT name, id FROM case_priorities WHERE tenant_id IS NULL"
    )).fetchall()
    priority_by_name = {row[0]: row[1] for row in pri_rows}

    for f in FORMULAS:
        logical_key = f["logical_key"]
        formula_id = _id("formula", logical_key)
        existing = conn.execute(sa.text(
            "SELECT 1 FROM prioritization_formulas "
            "WHERE tenant_id IS NULL AND logical_key = :k AND version = 1 LIMIT 1"
        ), {"k": logical_key}).fetchone()
        if not existing:
            conn.execute(sa.text(
                "INSERT INTO prioritization_formulas "
                "(id, tenant_id, logical_key, version, name, description, "
                " is_active, effective_from, created_at, created_by) "
                "VALUES (:id, NULL, :k, 1, :name, :desc, true, NOW(), NOW(), :uid)"
            ), {
                "id": formula_id, "k": logical_key,
                "name": f["name"], "desc": f["description"], "uid": user_id,
            })

        # Formula criteria (weights)
        for crit_code, weight in f["weights"].items():
            crit_id = _id("criterion", crit_code)
            existing_fc = conn.execute(sa.text(
                "SELECT 1 FROM prioritization_formula_criteria "
                "WHERE formula_id = :f AND criterion_id = :c LIMIT 1"
            ), {"f": formula_id, "c": crit_id}).fetchone()
            if existing_fc:
                continue
            conn.execute(sa.text(
                "INSERT INTO prioritization_formula_criteria "
                "(id, formula_id, criterion_id, weight, sort_order) "
                "VALUES (:id, :f, :c, :w, 0)"
            ), {
                "id": _id("fc", f"{logical_key}:{crit_code}"),
                "f": formula_id, "c": crit_id, "w": weight,
            })

        # Thresholds
        for min_v, max_v, pri_name in f["thresholds"]:
            pri_id = priority_by_name.get(pri_name)
            if not pri_id:
                # Skip silently if priority missing — plan documents in TODO
                continue
            existing_t = conn.execute(sa.text(
                "SELECT 1 FROM prioritization_thresholds "
                "WHERE formula_id = :f AND min_value = :mn AND max_value = :mx LIMIT 1"
            ), {"f": formula_id, "mn": min_v, "mx": max_v}).fetchone()
            if existing_t:
                continue
            conn.execute(sa.text(
                "INSERT INTO prioritization_thresholds "
                "(id, formula_id, min_value, max_value, priority_id, sort_order) "
                "VALUES (:id, :f, :mn, :mx, :p, 0)"
            ), {
                "id": _id("threshold", f"{logical_key}:{min_v}-{max_v}"),
                "f": formula_id, "mn": min_v, "mx": max_v, "p": pri_id,
            })


def downgrade() -> None:
    conn = op.get_bind()
    # Cascade-delete formulas → criteria + thresholds (via FK ON DELETE CASCADE)
    for f in FORMULAS:
        conn.execute(sa.text(
            "DELETE FROM prioritization_formulas "
            "WHERE tenant_id IS NULL AND logical_key = :k"
        ), {"k": f["logical_key"]})
    # Cascade-delete criteria → scales
    for code, *_ in CRITERIA:
        conn.execute(sa.text(
            "DELETE FROM prioritization_criteria "
            "WHERE tenant_id IS NULL AND code = :c"
        ), {"c": code})
    conn.execute(sa.text(
        "DELETE FROM permissions WHERE module = 'prioritization'"
    ))
