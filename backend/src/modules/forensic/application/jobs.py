"""Forensic background jobs (APScheduler).

Two recurring jobs run from the FastAPI lifespan:

- ``_scheduled_check_hunt_timeouts`` (every 120s): mark hunts whose
  ``timeout_at`` has elapsed as ``status='timeout'`` and best-effort
  cancel the corresponding Velociraptor hunt. Reaper pattern — Velo
  itself may also time out the hunt, but we surface the state to the
  operator without waiting for the next poll.
- ``_scheduled_sync_catalog`` (daily 02:30 UTC): pull artifact catalog
  from Velociraptor for every tenant with ``velo_org_id`` set.

Both are idempotent and safe to retry. ``start_forensic_jobs`` /
``stop_forensic_jobs`` are wired by Task 14 from ``main.py`` lifespan.
"""
import logging
from datetime import datetime, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.src.modules.forensic.infrastructure.models import (
    ForensicHuntModel,
)
from backend.src.modules.forensic.infrastructure.velo_client import (
    get_velo_client,
)

logger = logging.getLogger(__name__)
_scheduler = AsyncIOScheduler()


async def check_hunt_timeouts_once(db: AsyncSession) -> int:
    """Single iteration of the timeout sweeper.

    Returns the number of hunts marked as ``timeout``. Best-effort cancels
    each in Velo too; if Velo is unreachable the CMS state still flips so
    operators see the correct status.
    """
    now = datetime.now(timezone.utc)
    stmt = select(ForensicHuntModel).where(
        ForensicHuntModel.status.in_(["pending", "starting", "running"]),
        ForensicHuntModel.timeout_at <= now,
    )
    result = await db.execute(stmt)
    hunts = list(result.scalars().all())

    velo_client = None
    for hunt in hunts:
        hunt.status = "timeout"
        hunt.completed_at = now
        prev_error = hunt.error or ""
        hunt.error = (
            prev_error + ("\n" if prev_error else "")
            + f"[Auto-timeout at {now.isoformat()}]"
        )
        if hunt.velo_hunt_id:
            try:
                if velo_client is None:
                    velo_client = get_velo_client()
                await velo_client.cancel_hunt(
                    org_id=hunt.velo_org_id, hunt_id=hunt.velo_hunt_id,
                )
            except Exception as e:
                logger.warning(
                    "Timeout-sweep cancel for hunt %s failed: %s",
                    hunt.id, e,
                )
    return len(hunts)


async def _scheduled_check_hunt_timeouts() -> None:
    from backend.src.core.database import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        n = await check_hunt_timeouts_once(db)
        await db.commit()
        if n > 0:
            logger.info(
                "Forensic timeout sweep marked %d hunt(s) as timeout", n
            )


async def _scheduled_sync_catalog() -> None:
    from backend.src.modules.forensic.application.catalog_sync import (
        sync_all_tenants,
    )
    try:
        await sync_all_tenants()
        logger.info("Forensic catalog sync complete")
    except Exception as e:
        logger.error("Forensic catalog sync failed: %s", e)


def start_forensic_jobs() -> None:
    """Register and start the forensic recurring jobs.

    Called from FastAPI lifespan startup (Task 14).
    """
    _scheduler.add_job(
        _scheduled_check_hunt_timeouts,
        "interval", seconds=120,
        id="forensic_hunt_timeout_check",
        replace_existing=True,
    )
    _scheduler.add_job(
        _scheduled_sync_catalog,
        "cron", hour=2, minute=30,
        id="velociraptor_catalog_sync",
        replace_existing=True,
    )
    if not _scheduler.running:
        _scheduler.start()
    logger.info("Forensic jobs scheduler started")


def stop_forensic_jobs() -> None:
    if _scheduler.running:
        _scheduler.shutdown(wait=False)
