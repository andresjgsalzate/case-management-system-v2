"""APScheduler jobs for n8n_bridge timeouts.

Two periodic scans:
- timeout_pending_approvals_once (every 60s): marks expired approvals as
  'timeout' and POSTs decision='timeout' to n8n's resume_url so the Wait
  Node continues.
- timeout_pending_triage_once (every 30s): transitions cases stuck in
  pending_triage past their pending_triage_until back to 'logged'.

Both jobs are designed to be idempotent — re-running after a partial failure
re-picks the same rows since status filters scope to the unfinished set.
"""
import logging
from datetime import datetime, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select


logger = logging.getLogger(__name__)
_scheduler = AsyncIOScheduler()


async def timeout_pending_approvals_once(db) -> int:
    """Scan + timeout expired pending approvals. Returns # processed."""
    from backend.src.modules.n8n_bridge.application.use_cases import (
        N8nBridgeUseCases,
    )
    from backend.src.modules.n8n_bridge.infrastructure.models import (
        ApprovalRequestModel,
    )

    now = datetime.now(timezone.utc)
    stmt = (
        select(ApprovalRequestModel.id)
        .where(
            ApprovalRequestModel.status == "pending",
            ApprovalRequestModel.timeout_at <= now,
        )
    )
    ids = (await db.execute(stmt)).scalars().all()
    if not ids:
        return 0

    uc = N8nBridgeUseCases(db=db)
    processed = 0
    for approval_id in ids:
        try:
            result = await uc._timeout_approval(approval_id)
            if result.get("ok"):
                processed += 1
        except Exception as exc:
            logger.error(
                "n8n_bridge approval timeout %s failed: %s",
                approval_id, exc,
            )
    return processed


async def timeout_pending_triage_once(db) -> int:
    """Transition expired pending_triage cases back to 'logged'."""
    from sqlalchemy import text as _t
    now = datetime.now(timezone.utc)

    # Single UPDATE keeps the operation atomic per row even though the join
    # is read-only — Postgres CTE returns the affected ids for logging.
    result = await db.execute(_t(
        """
        UPDATE cases SET
            status_id = (SELECT id FROM case_statuses WHERE slug = 'logged'),
            pending_triage_until = NULL,
            updated_at = NOW()
        WHERE status_id = (
            SELECT id FROM case_statuses WHERE slug = 'pending_triage'
        )
          AND pending_triage_until IS NOT NULL
          AND pending_triage_until <= :now
        RETURNING id
        """
    ), {"now": now})
    transitioned = result.fetchall()
    await db.commit()
    if transitioned:
        logger.info(
            "n8n_bridge transitioned %d expired pending_triage cases",
            len(transitioned),
        )
    return len(transitioned)


# ── APScheduler wiring ────────────────────────────────────────────────


async def _scheduled_approvals_timeout() -> None:
    from backend.src.core.database import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        n = await timeout_pending_approvals_once(db)
        if n > 0:
            logger.info("n8n_bridge: %d approvals timed out", n)


async def _scheduled_triage_timeout() -> None:
    from backend.src.core.database import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        await timeout_pending_triage_once(db)


def start_n8n_jobs(
    approvals_interval_seconds: int = 60,
    triage_interval_seconds: int = 30,
) -> None:
    _scheduler.add_job(
        _scheduled_approvals_timeout, "interval",
        seconds=approvals_interval_seconds,
        id="approvals_timeout_check", replace_existing=True,
    )
    _scheduler.add_job(
        _scheduled_triage_timeout, "interval",
        seconds=triage_interval_seconds,
        id="triage_timeout_check", replace_existing=True,
    )
    if not _scheduler.running:
        _scheduler.start()


def stop_n8n_jobs() -> None:
    if _scheduler.running:
        _scheduler.shutdown(wait=False)
