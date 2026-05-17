"""Pure functions that compute the dashboard widgets from existing tables.

No persistence beyond `integration_health` (already populated by Task 4 job).
Each function takes (db, tenant_id) and returns the slim shape consumed by
DashboardSummaryDTO.

`compute_kpis` returns None for individual KPIs when the source data is
absent — better honest "no data" than a misleading 0.0%.
"""
from datetime import datetime, timedelta, timezone

from sqlalchemy import text as _t


# ── Severity counters ─────────────────────────────────────────────────


async def severity_counters(db, tenant_id: str) -> dict[str, int]:
    """Count open cases (non-final status) grouped by case_priorities.name.
    Lowercases the key so the UI can render against fixed buckets without
    worrying about Spanish capitalization variations."""
    row = (await db.execute(_t(
        """
        SELECT p.name AS priority_name, COUNT(c.id) AS n
        FROM cases c
        JOIN case_statuses s ON s.id = c.status_id
        JOIN case_priorities p ON p.id = c.priority_id
        WHERE c.tenant_id = :t AND s.is_final = false
        GROUP BY p.name
        """
    ), {"t": tenant_id})).all()
    return {priority.lower(): n for priority, n in row}


# ── KPIs ──────────────────────────────────────────────────────────────


async def compute_kpis(db, tenant_id: str, period_hours: int = 24) -> dict:
    """24-hour rolling KPIs. None where data is insufficient."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=period_hours)

    # cases_per_hour = cases created in window / period
    created_count = (await db.execute(_t(
        "SELECT COUNT(*) FROM cases WHERE tenant_id = :t AND created_at >= :c"
    ), {"t": tenant_id, "c": cutoff})).scalar_one()
    cases_per_hour = (
        round(created_count / period_hours, 2) if period_hours > 0 else None
    )

    # MTTR = avg(closed_at - created_at) for cases closed in window
    mttr_row = (await db.execute(_t(
        """
        SELECT AVG(EXTRACT(EPOCH FROM (closed_at - created_at)) / 60.0)
        FROM cases
        WHERE tenant_id = :t
          AND closed_at IS NOT NULL
          AND closed_at >= :c
        """
    ), {"t": tenant_id, "c": cutoff})).scalar_one_or_none()
    mttr_minutes = round(mttr_row, 1) if mttr_row is not None else None

    # MTTD = avg(case.created_at - inbound_event.received_at) for cases linked
    # to an inbound_event whose case was created in the window. Only meaningful
    # for SOC-pipeline cases — manual cases return None.
    mttd_row = (await db.execute(_t(
        """
        SELECT AVG(EXTRACT(EPOCH FROM (c.created_at - ie.received_at)) / 60.0)
        FROM cases c
        JOIN inbound_events ie ON ie.case_id = c.id
        WHERE c.tenant_id = :t AND c.created_at >= :cutoff
        """
    ), {"t": tenant_id, "cutoff": cutoff})).scalar_one_or_none()
    mttd_minutes = round(mttd_row, 1) if mttd_row is not None else None

    return {
        "period_hours": period_hours,
        "cases_per_hour": cases_per_hour,
        "mttr_minutes": mttr_minutes,
        "mttd_minutes": mttd_minutes,
        # SLA + FP rate depend on modules that aren't fully wired in Phase 1 —
        # leave as None until the contract with sla/dispositions firms up.
        "sla_compliance_pct": None,
        "false_positive_rate_pct": None,
    }


# ── Recent events / health ────────────────────────────────────────────


async def recent_inbound_events(db, tenant_id: str, limit: int = 20):
    """Last N inbound events for the live feed."""
    rows = (await db.execute(_t(
        """
        SELECT id, source_id, received_at, status, case_id
        FROM inbound_events
        WHERE tenant_id = :t
        ORDER BY received_at DESC
        LIMIT :n
        """
    ), {"t": tenant_id, "n": limit})).all()
    return [
        {
            "id": r[0], "source_id": r[1], "received_at": r[2],
            "status": r[3], "case_id": r[4],
        }
        for r in rows
    ]


async def integration_health_summary(db, tenant_id: str):
    """Latest snapshot per source belonging to `tenant_id`."""
    rows = (await db.execute(_t(
        """
        SELECT DISTINCT ON (h.source_id)
            h.source_id, s.name AS source_name, h.status, h.recorded_at,
            h.events_received_5min, h.events_processed_5min,
            h.events_failed_5min, h.avg_latency_ms_5min
        FROM integration_health h
        JOIN integration_sources s ON s.id = h.source_id
        WHERE s.tenant_id = :t
        ORDER BY h.source_id, h.recorded_at DESC
        """
    ), {"t": tenant_id})).all()
    return [
        {
            "source_id": r[0], "source_name": r[1], "status": r[2],
            "recorded_at": r[3],
            "events_received_5min": r[4],
            "events_processed_5min": r[5],
            "events_failed_5min": r[6],
            "avg_latency_ms_5min": r[7],
        }
        for r in rows
    ]


# ── Approvals summary ─────────────────────────────────────────────────


async def pending_approvals_summary(db, tenant_id: str, top_n: int = 5):
    """Returns (top N rows, total count) for pending approvals widget."""
    total = (await db.execute(_t(
        "SELECT COUNT(*) FROM approval_requests "
        "WHERE tenant_id = :t AND status = 'pending'"
    ), {"t": tenant_id})).scalar_one()
    rows = (await db.execute(_t(
        """
        SELECT id, case_id, requested_action, action_category,
               requested_by_workflow, timeout_at, created_at
        FROM approval_requests
        WHERE tenant_id = :t AND status = 'pending'
        ORDER BY timeout_at ASC
        LIMIT :n
        """
    ), {"t": tenant_id, "n": top_n})).all()
    return total, [
        {
            "id": r[0], "case_id": r[1], "requested_action": r[2],
            "action_category": r[3], "requested_by_workflow": r[4],
            "timeout_at": r[5], "created_at": r[6],
        }
        for r in rows
    ]
