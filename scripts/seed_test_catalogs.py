"""Seed minimal global catalogs for end-to-end case creation tests.

Creates 4 tables of reference data (tenant_id = NULL = global, visible
to every tenant):

  - case_statuses   : New, In Progress, Resolved, Closed
  - case_priorities : Baja, Media, Alta, Critica
  - applications    : CMS Core, Email, Network
  - origins         : Manual, Email, API

Idempotent: re-running is a no-op (uses ON CONFLICT on the natural keys
already present in the schema -- (tenant_id, code) for apps/origins,
slug for statuses, level for priorities).

allowed_transitions on statuses is wired so the flow is:
  New -> In Progress -> Resolved -> Closed

Connects to Postgres via the same env var the backend uses.
"""
from __future__ import annotations

import os
import sys
import uuid
from contextlib import contextmanager

import psycopg2
from psycopg2.extras import Json


def _load_env() -> dict[str, str]:
    """Pull DATABASE_URL (or PG_* fallback) from backend/.env."""
    env: dict[str, str] = {}
    env_path = "backend/.env"
    if os.path.exists(env_path):
        with open(env_path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                env[k] = v.strip('"').strip("'")
    return env


def _connect():
    env = _load_env()
    # Backend uses DATABASE_URL in async form (postgresql+asyncpg://...).
    # psycopg2 wants sync form; substitute the driver.
    url = env.get("DATABASE_URL", "")
    if url.startswith("postgresql+asyncpg://"):
        url = url.replace("postgresql+asyncpg://", "postgresql://", 1)
    if not url:
        # Fallback: docker-compose maps cms_postgres to localhost:5433.
        url = "postgresql://cms_user:cms_password@localhost:5433/cms_dev"
    return psycopg2.connect(url)


# ─── Status definitions: slug -> (name, color, order, is_initial, is_final) ──
STATUSES: list[tuple[str, str, str, int, bool, bool]] = [
    ("new",         "Nuevo",       "#3b82f6", 10, True,  False),
    ("in_progress", "En progreso", "#f59e0b", 20, False, False),
    ("resolved",    "Resuelto",    "#10b981", 30, False, True),
    ("closed",      "Cerrado",     "#6b7280", 40, False, True),
]

# Linear flow: new -> in_progress -> resolved -> closed.
# Final states (resolved/closed) have no further transitions.
TRANSITIONS = {
    "new":         ["in_progress"],
    "in_progress": ["resolved", "closed"],  # allow direct close (e.g. duplicates)
    "resolved":    ["closed"],
    "closed":      [],
}

# Priority definitions: (name, level, color, is_default)
PRIORITIES: list[tuple[str, int, str, bool]] = [
    ("Baja",     1, "#10b981", False),
    ("Media",    2, "#f59e0b", True),   # default
    ("Alta",     3, "#ef4444", False),
    ("Critica",  4, "#7f1d1d", False),
]

# Application definitions: (code, name, description)
APPLICATIONS: list[tuple[str, str, str]] = [
    ("CMS",   "CMS Core",      "Aplicaciones internas del CMS"),
    ("EMAIL", "Email Service", "Servidores de correo corporativo"),
    ("NET",   "Network",       "Infraestructura de red"),
]

# Origin definitions: (code, name, description)
ORIGINS: list[tuple[str, str, str]] = [
    ("MANUAL", "Manual",     "Creado manualmente por un operador"),
    ("EMAIL",  "Email",      "Recibido desde una alerta por email"),
    ("API",    "API",        "Disparado vía integración API"),
]


@contextmanager
def _tx(conn):
    """Single-transaction context that commits on success, rolls back on error."""
    try:
        yield conn.cursor()
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def _seed_statuses(cur) -> dict[str, str]:
    """First pass: insert all statuses with empty transitions. Returns
    slug -> id map. Second pass below fills allowed_transitions once we
    know all ids.

    The split is needed because allowed_transitions stores ids, and we
    can't reference a row that hasn't been inserted yet within the same
    statement.
    """
    slug_to_id: dict[str, str] = {}
    for slug, name, color, order, is_initial, is_final in STATUSES:
        # Look up existing first (idempotent)
        cur.execute(
            "SELECT id FROM case_statuses WHERE tenant_id IS NULL AND slug = %s",
            (slug,),
        )
        row = cur.fetchone()
        if row:
            slug_to_id[slug] = row[0]
            continue
        sid = str(uuid.uuid4())
        cur.execute(
            """
            INSERT INTO case_statuses
              (id, tenant_id, name, slug, color, "order",
               is_initial, is_final, allowed_transitions, created_at,
               pauses_sla, applies_to_case_types)
            VALUES
              (%s, NULL, %s, %s, %s, %s,
               %s, %s, %s, NOW(),
               false, %s)
            """,
            (
                sid, name, slug, color, order,
                is_initial, is_final, Json([]),
                Json(["request", "incident", "event"]),
            ),
        )
        slug_to_id[slug] = sid
    return slug_to_id


def _wire_transitions(cur, slug_to_id: dict[str, str]) -> None:
    for slug, next_slugs in TRANSITIONS.items():
        target_ids = [slug_to_id[s] for s in next_slugs if s in slug_to_id]
        cur.execute(
            "UPDATE case_statuses SET allowed_transitions = %s "
            "WHERE id = %s",
            (Json(target_ids), slug_to_id[slug]),
        )


def _seed_priorities(cur) -> None:
    for name, level, color, is_default in PRIORITIES:
        cur.execute(
            "SELECT id FROM case_priorities "
            "WHERE tenant_id IS NULL AND level = %s",
            (level,),
        )
        if cur.fetchone():
            continue
        cur.execute(
            """
            INSERT INTO case_priorities
              (id, tenant_id, name, level, color,
               is_default, is_active, created_at)
            VALUES
              (%s, NULL, %s, %s, %s, %s, true, NOW())
            """,
            (str(uuid.uuid4()), name, level, color, is_default),
        )


def _seed_applications(cur) -> None:
    for code, name, desc in APPLICATIONS:
        cur.execute(
            "SELECT id FROM applications "
            "WHERE tenant_id IS NULL AND code = %s",
            (code,),
        )
        if cur.fetchone():
            continue
        cur.execute(
            """
            INSERT INTO applications
              (id, tenant_id, name, code, description, is_active, created_at)
            VALUES
              (%s, NULL, %s, %s, %s, true, NOW())
            """,
            (str(uuid.uuid4()), name, code, desc),
        )


def _seed_origins(cur) -> None:
    for code, name, desc in ORIGINS:
        cur.execute(
            "SELECT id FROM origins "
            "WHERE tenant_id IS NULL AND code = %s",
            (code,),
        )
        if cur.fetchone():
            continue
        cur.execute(
            """
            INSERT INTO origins
              (id, tenant_id, name, code, description, is_active)
            VALUES
              (%s, NULL, %s, %s, %s, true)
            """,
            (str(uuid.uuid4()), name, code, desc),
        )


def main() -> None:
    conn = _connect()
    try:
        with _tx(conn) as cur:
            slug_to_id = _seed_statuses(cur)
            _wire_transitions(cur, slug_to_id)
            _seed_priorities(cur)
            _seed_applications(cur)
            _seed_origins(cur)
            # Final counts for report
            cur.execute(
                """
                SELECT 'case_statuses' AS tbl, COUNT(*) FROM case_statuses
                UNION ALL SELECT 'case_priorities', COUNT(*) FROM case_priorities
                UNION ALL SELECT 'applications',    COUNT(*) FROM applications
                UNION ALL SELECT 'origins',         COUNT(*) FROM origins
                ORDER BY tbl
                """
            )
            print("Seed complete. Row counts:")
            for tbl, count in cur.fetchall():
                print(f"  {tbl:18s} = {count}")
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
