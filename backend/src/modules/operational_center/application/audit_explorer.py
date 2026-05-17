"""Cross-system audit query — UNION ALL across multiple audit tables.

Phase 1 sources (all with native tenant_id column):
- activity_entries           (case-scoped activity feed)
- audit_logs                 (generic audit module)
- inbound_events             (security events received from integrations)

Phase 2 sources requiring JOIN to derive tenant_id (deferred):
- security_taxonomies_audit_log → join security_taxonomies
- playbook_run_callbacks       → join playbook_runs
- case_priority_calculations   → join cases

Output rows normalize to AuditEventDTO shape so the UI renders one
homogeneous timeline.
"""
import csv
import io
import json
from datetime import datetime
from typing import Any

from sqlalchemy import text as _t


# Sources the operator can filter by. Adding a new source here requires
# adding the corresponding subquery branch in _build_query.
ALL_SOURCES = ("activity", "audit", "inbound_event")


class AuditFilters:
    """Plain-old container for query parameters (kept out of Pydantic to
    avoid coupling the query builder to the DTO layer)."""

    def __init__(
        self,
        *,
        tenant_id: str,
        case_id: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        sources: list[str] | None = None,
        search: str | None = None,
        limit: int = 200,
        offset: int = 0,
    ):
        self.tenant_id = tenant_id
        self.case_id = case_id
        self.date_from = date_from
        self.date_to = date_to
        self.sources = (
            [s for s in sources if s in ALL_SOURCES]
            if sources else list(ALL_SOURCES)
        )
        self.search = search
        self.limit = max(1, min(limit, 500))
        self.offset = max(0, offset)


def _build_query(filters: AuditFilters) -> tuple[str, dict]:
    """Build the raw SQL UNION ALL with parametrized filters."""
    params: dict[str, Any] = {
        "tenant_id": filters.tenant_id, "case_id": filters.case_id,
        "date_from": filters.date_from, "date_to": filters.date_to,
        "limit": filters.limit, "offset": filters.offset,
        "search": f"%{filters.search}%" if filters.search else None,
    }

    parts: list[str] = []

    # ── activity_entries → 'activity'
    if "activity" in filters.sources:
        parts.append("""
            SELECT
                'activity' AS source_table,
                id AS event_id,
                created_at AS occurred_at,
                case_id,
                actor_id,
                event_type || ': ' || description AS summary,
                payload AS extra
            FROM activity_entries
            WHERE tenant_id = :tenant_id
              AND (CAST(:case_id AS varchar) IS NULL OR case_id = CAST(:case_id AS varchar))
              AND (CAST(:date_from AS timestamptz) IS NULL OR created_at >= CAST(:date_from AS timestamptz))
              AND (CAST(:date_to AS timestamptz) IS NULL OR created_at <= CAST(:date_to AS timestamptz))
              AND (CAST(:search AS varchar) IS NULL OR description ILIKE CAST(:search AS varchar)
                   OR event_type ILIKE CAST(:search AS varchar))
        """)

    # ── audit_logs → 'audit'
    if "audit" in filters.sources:
        parts.append("""
            SELECT
                'audit' AS source_table,
                id AS event_id,
                created_at AS occurred_at,
                NULL::varchar AS case_id,
                actor_id,
                action || ' ' || entity_type || ' ' || entity_id AS summary,
                changes AS extra
            FROM audit_logs
            WHERE tenant_id = :tenant_id
              AND (CAST(:case_id AS varchar) IS NULL OR entity_id = CAST(:case_id AS varchar))
              AND (CAST(:date_from AS timestamptz) IS NULL OR created_at >= CAST(:date_from AS timestamptz))
              AND (CAST(:date_to AS timestamptz) IS NULL OR created_at <= CAST(:date_to AS timestamptz))
              AND (CAST(:search AS varchar) IS NULL OR entity_type ILIKE CAST(:search AS varchar)
                   OR action ILIKE CAST(:search AS varchar) OR entity_id ILIKE CAST(:search AS varchar))
        """)

    # ── inbound_events → 'inbound_event'
    if "inbound_event" in filters.sources:
        parts.append("""
            SELECT
                'inbound_event' AS source_table,
                id AS event_id,
                received_at AS occurred_at,
                case_id,
                NULL::varchar AS actor_id,
                'inbound: status=' || status ||
                  COALESCE(' last_error=' || left(last_error, 200), '') AS summary,
                raw_payload AS extra
            FROM inbound_events
            WHERE tenant_id = :tenant_id
              AND (CAST(:case_id AS varchar) IS NULL OR case_id = CAST(:case_id AS varchar))
              AND (CAST(:date_from AS timestamptz) IS NULL OR received_at >= CAST(:date_from AS timestamptz))
              AND (CAST(:date_to AS timestamptz) IS NULL OR received_at <= CAST(:date_to AS timestamptz))
              AND (CAST(:search AS varchar) IS NULL OR status ILIKE CAST(:search AS varchar)
                   OR COALESCE(last_error, '') ILIKE CAST(:search AS varchar))
        """)

    if not parts:
        # No sources requested — empty UNION would crash, return a no-op SQL
        return "SELECT 1 WHERE false", {"limit": 0, "offset": 0}

    union_sql = " UNION ALL ".join(parts)
    paged_sql = (
        f"SELECT * FROM ({union_sql}) u "
        f"ORDER BY occurred_at DESC "
        f"LIMIT :limit OFFSET :offset"
    )
    return paged_sql, params


def _build_count_query(filters: AuditFilters) -> tuple[str, dict]:
    """Same UNION but wrapped in COUNT(*) — no LIMIT/OFFSET."""
    sql, params = _build_query(filters)
    if "FROM (" not in sql:
        return "SELECT 0", {}
    # Strip the outer ORDER BY / LIMIT / OFFSET (everything from ' u ' on)
    inner = sql.split("FROM (")[1].rsplit(") u ", 1)[0]
    count_sql = f"SELECT COUNT(*) FROM ({inner}) u"
    # COUNT query doesn't bind limit/offset
    count_params = {k: v for k, v in params.items() if k not in ("limit", "offset")}
    return count_sql, count_params


# ── Public API ────────────────────────────────────────────────────────


async def query_audit_events(db, filters: AuditFilters) -> dict:
    """Returns {events: [...normalized rows], total: int}."""
    sql, params = _build_query(filters)
    rows = (await db.execute(_t(sql), params)).all()

    count_sql, count_params = _build_count_query(filters)
    total = (await db.execute(_t(count_sql), count_params)).scalar_one() if count_sql else 0

    events = [
        {
            "source_table": r[0],
            "event_id": r[1],
            "occurred_at": r[2],
            "case_id": r[3],
            "actor_id": r[4],
            "summary": r[5],
            "extra": r[6],
        }
        for r in rows
    ]
    return {"events": events, "total": int(total)}


async def export_audit_events_csv(db, filters: AuditFilters) -> str:
    """Returns a CSV string of audit events. For huge exports, swap to a
    StreamingResponse + generator — Phase 1 keeps it in-memory."""
    # Force a generous limit for export — caller is responsible for not
    # asking for the whole DB.
    export_filters = AuditFilters(
        tenant_id=filters.tenant_id, case_id=filters.case_id,
        date_from=filters.date_from, date_to=filters.date_to,
        sources=filters.sources, search=filters.search,
        limit=min(filters.limit * 10, 5000), offset=0,
    )
    result = await query_audit_events(db, export_filters)

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([
        "source_table", "event_id", "occurred_at", "case_id",
        "actor_id", "summary", "extra_json",
    ])
    for e in result["events"]:
        writer.writerow([
            e["source_table"], e["event_id"],
            e["occurred_at"].isoformat() if e["occurred_at"] else "",
            e["case_id"] or "", e["actor_id"] or "",
            e["summary"], json.dumps(e["extra"], default=str) if e["extra"] else "",
        ])
    return buf.getvalue()
