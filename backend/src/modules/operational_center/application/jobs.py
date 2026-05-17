"""APScheduler jobs for the operational_center module.

Two periodic scans:
- refresh_integration_health_once (every 60s): for each active source,
  compute 5-min metrics from inbound_events + derive status (healthy /
  degraded / down) + persist an integration_health row + emit a
  transition event when status changes.
- cleanup_old_integration_health_once (daily 3am): purge rows older than
  30 days so the table doesn't grow unboundedly.

Per spec §4.6, source-type-specific probes can register via
register_health_probe() to enrich `extra_metrics` with vendor data
(e.g. last Wazuh manager heartbeat). Probes failing yield {"error": ...}
in extra_metrics rather than skipping the row.
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import Awaitable, Callable

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import delete, select
from sqlalchemy import text as _t


logger = logging.getLogger(__name__)
_scheduler = AsyncIOScheduler()

# Source-type-specific probe registry. Each probe takes the source row and
# returns an extra_metrics dict that lands in integration_health.extra_metrics.
HEALTH_PROBES: dict[str, Callable[..., Awaitable[dict]]] = {}


def register_health_probe(
    source_type: str, probe_fn: Callable[..., Awaitable[dict]],
) -> None:
    HEALTH_PROBES[source_type] = probe_fn


# ── Status classification ─────────────────────────────────────────────


def classify_health_status(
    *,
    received: int,
    failed: int,
    avg_latency_ms: int | None,
    seconds_since_last_event: float,
) -> str:
    """Pure decision function for testability.

    - 'down'      : no event in last 10 minutes
    - 'degraded'  : failure rate > 30%, OR avg latency > 5000ms
    - 'healthy'   : everything else (incl. window with zero events but
                    recent activity outside the 5-min window)
    """
    if seconds_since_last_event > 600:
        return "down"
    if received > 0 and (failed / received) > 0.30:
        return "degraded"
    if avg_latency_ms is not None and avg_latency_ms > 5000:
        return "degraded"
    return "healthy"


# ── Metrics computation ───────────────────────────────────────────────


async def compute_metrics(
    db, source_id: str, window_minutes: int = 5,
) -> dict:
    """Aggregate inbound_events stats for `source_id` over the last window."""
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=window_minutes)
    row = (await db.execute(_t(
        """
        SELECT
            COUNT(*) AS received,
            SUM(CASE WHEN status = 'processed' THEN 1 ELSE 0 END) AS processed,
            SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) AS failed,
            AVG(
                EXTRACT(EPOCH FROM (processed_at - received_at)) * 1000
            ) FILTER (WHERE processed_at IS NOT NULL) AS avg_latency_ms
        FROM inbound_events
        WHERE source_id = :sid AND received_at >= :cutoff
        """
    ), {"sid": source_id, "cutoff": cutoff})).first()
    return {
        "received": int(row[0] or 0),
        "processed": int(row[1] or 0),
        "failed": int(row[2] or 0),
        "avg_latency_ms": int(row[3]) if row[3] is not None else None,
    }


# ── Refresh job ───────────────────────────────────────────────────────


async def refresh_integration_health_once(db) -> int:
    """Compute + persist one health snapshot per active source.
    Returns # of sources processed."""
    from backend.src.modules.integrations.infrastructure.models import (
        IntegrationSourceModel,
    )
    from backend.src.modules.operational_center.infrastructure.models import (
        IntegrationHealthModel,
    )

    sources = (await db.execute(
        select(IntegrationSourceModel)
        .where(IntegrationSourceModel.is_active.is_(True))
    )).scalars().all()

    if not sources:
        return 0

    now = datetime.now(timezone.utc)
    for source in sources:
        metrics = await compute_metrics(db, source.id, window_minutes=5)
        seconds_since_last_event = (
            (now - source.last_event_received_at).total_seconds()
            if source.last_event_received_at else float("inf")
        )
        status = classify_health_status(
            received=metrics["received"],
            failed=metrics["failed"],
            avg_latency_ms=metrics["avg_latency_ms"],
            seconds_since_last_event=seconds_since_last_event,
        )

        # Run optional source-type-specific probe for extra_metrics
        extra: dict = {}
        probe = HEALTH_PROBES.get(source.source_type)
        if probe:
            try:
                extra = await probe(source) or {}
            except Exception as e:
                extra = {"error": f"{type(e).__name__}: {str(e)[:200]}"}

        # Detect transition vs previous snapshot
        previous_row = (await db.execute(_t(
            "SELECT status FROM integration_health "
            "WHERE source_id = :sid ORDER BY recorded_at DESC LIMIT 1"
        ), {"sid": source.id})).first()
        previous_status = previous_row[0] if previous_row else None

        db.add(IntegrationHealthModel(
            source_id=source.id,
            events_received_5min=metrics["received"],
            events_processed_5min=metrics["processed"],
            events_failed_5min=metrics["failed"],
            avg_latency_ms_5min=metrics["avg_latency_ms"],
            status=status,
            extra_metrics=extra or None,
        ))

        # Emit transition event so the SSE stream (Task 4 follow-up) /
        # alerting (Sub-spec 08) can react.
        if previous_status and previous_status != status:
            from backend.src.core.events.bus import get_event_bus
            from backend.src.core.events.base import BaseEvent
            event_name = (
                "integration_health.recovered" if status == "healthy"
                else "integration_health.degraded"
            )
            try:
                await get_event_bus().publish(BaseEvent(
                    event_name=event_name,
                    tenant_id=source.tenant_id or "default",
                    payload={
                        "source_id": source.id,
                        "source_name": source.name,
                        "previous_status": previous_status,
                        "new_status": status,
                        "tenant_id": source.tenant_id,
                    },
                ))
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "integration_health transition event publish failed: %s",
                    exc,
                )

    await db.commit()
    return len(sources)


# ── Cleanup job ───────────────────────────────────────────────────────


async def cleanup_old_integration_health_once(db, days: int = 30) -> int:
    """Delete integration_health rows older than `days`. Returns rowcount."""
    from backend.src.modules.operational_center.infrastructure.models import (
        IntegrationHealthModel,
    )
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    result = await db.execute(
        delete(IntegrationHealthModel)
        .where(IntegrationHealthModel.recorded_at < cutoff)
    )
    await db.commit()
    return result.rowcount or 0


# ── APScheduler wiring ────────────────────────────────────────────────


async def _scheduled_refresh() -> None:
    from backend.src.core.database import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        n = await refresh_integration_health_once(db)
        if n > 0:
            logger.info("operational_center: refreshed %d sources", n)


async def _scheduled_cleanup() -> None:
    from backend.src.core.database import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        deleted = await cleanup_old_integration_health_once(db)
        if deleted:
            logger.info(
                "operational_center: pruned %d integration_health rows", deleted,
            )


def start_operational_jobs(refresh_seconds: int = 60) -> None:
    _scheduler.add_job(
        _scheduled_refresh, "interval", seconds=refresh_seconds,
        id="integration_health_refresh", replace_existing=True,
    )
    _scheduler.add_job(
        _scheduled_cleanup, "cron", hour=3, minute=0,
        id="integration_health_cleanup", replace_existing=True,
    )
    if not _scheduler.running:
        _scheduler.start()


def stop_operational_jobs() -> None:
    if _scheduler.running:
        _scheduler.shutdown(wait=False)
