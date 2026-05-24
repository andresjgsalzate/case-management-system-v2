"""Seed the SOC triage catalog tables (Phase 2 of docs/specs/triage.md).

Idempotent: re-running produces no changes (lookup-then-insert by name).

Creates:

  1. triage_tool_types     -- 15 tools from xlsx `Herramientas!R9-R23`
  2. triage_tool_actions   -- Monitoreo, Bloqueo
  3. case_priorities       -- ADD "Falso Positivo" if missing (other 4
                              priorities are seeded by seed_test_catalogs.py)
  4. triage_sla_policies   -- 5 entries mapping priority -> SLA minutes
                              (xlsx `Priorización!R18-R22`)

All rows are inserted with tenant_id=NULL (= global). Run from repo root:
  python3 scripts/seed_triage_catalogs.py
"""
from __future__ import annotations

import os
import sys
import uuid
from contextlib import contextmanager

import psycopg2


# ─── Data (literal from xlsx) ───────────────────────────────────────


# xlsx Herramientas R9-R23 (15 items; NGFWG kept literal -- see import_taxonomy
# script for context on the trailing G).
TOOL_TYPES: list[str] = [
    "FW Externo", "FW Interno", "AD-Controller", "EDR", "Server", "WAF",
    "Base de datos", "Equipos Red", "Linux", "Office365", "ZTNA",
    "AntiSPAM", "Backup", "Equipos de computo", "NGFWG",
]

# xlsx Triage!R17 col C ("Acción aplicada") -- only 2 values seen but the
# catalog is extensible from /settings.
TOOL_ACTIONS: list[str] = ["Monitoreo", "Bloqueo"]

# xlsx Priorización!R18-R22. priority_name -> sla_minutes (NULL = N/A).
# Names use feminine forms to match the seeded case_priorities rows
# (la prioridad es alta -- agrees in gender).
SLA_BY_PRIORITY: dict[str, int | None] = {
    "Critica":        20,
    "Alta":           40,
    "Media":          120,
    "Baja":           720,    # 12 hours
    "Falso Positivo": None,   # N/A
}


# ─── DB helpers (same pattern as seed_test_catalogs.py) ─────────────


def _load_env() -> dict[str, str]:
    env: dict[str, str] = {}
    if os.path.exists("backend/.env"):
        with open("backend/.env", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                env[k] = v.strip('"').strip("'")
    return env


def _connect():
    url = _load_env().get("DATABASE_URL", "")
    if url.startswith("postgresql+asyncpg://"):
        url = url.replace("postgresql+asyncpg://", "postgresql://", 1)
    if not url:
        url = "postgresql://cms_user:cms_password@localhost:5433/cms_dev"
    return psycopg2.connect(url)


@contextmanager
def _tx(conn):
    try:
        yield conn.cursor()
        conn.commit()
    except Exception:
        conn.rollback()
        raise


# ─── Seeding ────────────────────────────────────────────────────────


def _seed_tool_types(cur) -> int:
    inserted = 0
    for name in TOOL_TYPES:
        cur.execute(
            "SELECT id FROM triage_tool_types "
            "WHERE tenant_id IS NULL AND name = %s",
            (name,),
        )
        if cur.fetchone():
            continue
        cur.execute(
            "INSERT INTO triage_tool_types "
            "(id, tenant_id, name, description, is_active, created_at) "
            "VALUES (%s, NULL, %s, NULL, true, NOW())",
            (str(uuid.uuid4()), name),
        )
        inserted += 1
    return inserted


def _seed_tool_actions(cur) -> int:
    inserted = 0
    for name in TOOL_ACTIONS:
        cur.execute(
            "SELECT id FROM triage_tool_actions "
            "WHERE tenant_id IS NULL AND name = %s",
            (name,),
        )
        if cur.fetchone():
            continue
        cur.execute(
            "INSERT INTO triage_tool_actions "
            "(id, tenant_id, name, is_active, created_at) "
            "VALUES (%s, NULL, %s, true, NOW())",
            (str(uuid.uuid4()), name),
        )
        inserted += 1
    return inserted


def _ensure_falso_positivo_priority(cur) -> str | None:
    """Add 'Falso Positivo' to case_priorities if missing. Returns its id."""
    cur.execute(
        "SELECT id FROM case_priorities "
        "WHERE tenant_id IS NULL AND name = 'Falso Positivo'"
    )
    row = cur.fetchone()
    if row:
        return row[0]
    pid = str(uuid.uuid4())
    cur.execute(
        """
        INSERT INTO case_priorities
          (id, tenant_id, name, level, color, is_default, is_active, created_at)
        VALUES (%s, NULL, 'Falso Positivo', 0, '#9ca3af', false, true, NOW())
        """,
        (pid,),
    )
    return pid


def _seed_sla_policies(cur) -> int:
    """Insert one row per priority -> sla_minutes mapping."""
    inserted = 0
    for priority_name, sla in SLA_BY_PRIORITY.items():
        # Resolve priority_id (global tenant). Skip if priority not seeded.
        cur.execute(
            "SELECT id FROM case_priorities "
            "WHERE tenant_id IS NULL AND name = %s",
            (priority_name,),
        )
        row = cur.fetchone()
        if not row:
            print(
                f"  [SKIP] priority '{priority_name}' not in DB -- "
                "run seed_test_catalogs.py first"
            )
            continue
        priority_id = row[0]
        cur.execute(
            "SELECT id FROM triage_sla_policies "
            "WHERE tenant_id IS NULL AND priority_id = %s",
            (priority_id,),
        )
        if cur.fetchone():
            continue
        cur.execute(
            """
            INSERT INTO triage_sla_policies
              (id, tenant_id, priority_id, sla_minutes, is_active, created_at)
            VALUES (%s, NULL, %s, %s, true, NOW())
            """,
            (str(uuid.uuid4()), priority_id, sla),
        )
        inserted += 1
    return inserted


# ─── Entry ──────────────────────────────────────────────────────────


def main() -> None:
    conn = _connect()
    try:
        with _tx(conn) as cur:
            print("Seeding triage catalogs...")

            n = _seed_tool_types(cur)
            print(f"  triage_tool_types:    +{n} (target {len(TOOL_TYPES)})")

            n = _seed_tool_actions(cur)
            print(f"  triage_tool_actions:  +{n} (target {len(TOOL_ACTIONS)})")

            _ensure_falso_positivo_priority(cur)
            print("  case_priorities:      Falso Positivo ensured")

            n = _seed_sla_policies(cur)
            print(f"  triage_sla_policies:  +{n} (target {len(SLA_BY_PRIORITY)})")

            # Summary
            cur.execute("SELECT COUNT(*) FROM triage_tool_types")
            tt = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM triage_tool_actions")
            ta = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM triage_sla_policies")
            sp = cur.fetchone()[0]
            print(
                f"\nFinal: {tt} tool_types, {ta} tool_actions, "
                f"{sp} sla_policies"
            )
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
