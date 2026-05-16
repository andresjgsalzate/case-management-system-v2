"""APScheduler jobs for inbound events processing.

`retry_pending_events_once` is the worker loop body: pulls up to BATCH_SIZE
pending rows (using SELECT FOR UPDATE SKIP LOCKED so concurrent workers don't
contend), commits to release locks, then dispatches each row through
`IntegrationsUseCases.process_event` with all UCs wired.

The scheduled wrapper (`start_inbound_jobs`) runs every 5 seconds by default.
Failures inside process_event are caught and logged; the inbound row is
already updated by `handle_processing_failure` so the next tick will pick it
up again if a retry is scheduled.
"""
import logging
from datetime import datetime, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import or_, select


logger = logging.getLogger(__name__)
_scheduler = AsyncIOScheduler()

BATCH_SIZE = 50

import os as _os


def _system_user_id() -> str:
    """Read INTEGRATIONS_SYSTEM_USER_ID lazily so tests can set it after import."""
    return _os.environ.get(
        "INTEGRATIONS_SYSTEM_USER_ID",
        "00000000-0000-0000-0000-000000000000",
    )


def _make_use_cases(db):
    """Build an IntegrationsUseCases with all peer modules wired.

    Local imports keep startup-time module graph clean — no SOC module is
    pulled in until the worker actually fires.
    """
    from backend.src.modules.cases.application.use_cases import CaseUseCases
    from backend.src.modules.integrations.application.use_cases import (
        IntegrationsUseCases,
    )
    from backend.src.modules.prioritization.application.use_cases import (
        PrioritizationUseCases,
    )
    from backend.src.modules.security_taxonomies.application.use_cases import (
        SecurityTaxonomyUseCases,
    )

    return IntegrationsUseCases(
        db=db,
        taxonomies_uc=SecurityTaxonomyUseCases(db=db),
        prioritization_uc=PrioritizationUseCases(db=db),
        cases_uc=CaseUseCases(db=db),
    )


async def retry_pending_events_once(db) -> int:
    """Claim up to BATCH_SIZE pending events and process them serially.

    Locks are released immediately after the SELECT so other workers can
    claim a different batch; `process_event` re-acquires a per-row lock
    via its own SELECT FOR UPDATE SKIP LOCKED.
    """
    from backend.src.modules.integrations.infrastructure.models import (
        InboundEventModel,
    )

    stmt = (
        select(InboundEventModel.id)
        .where(
            InboundEventModel.status == "pending",
            or_(
                InboundEventModel.next_retry_at.is_(None),
                InboundEventModel.next_retry_at <= datetime.now(timezone.utc),
            ),
        )
        .order_by(InboundEventModel.received_at)
        .with_for_update(skip_locked=True)
        .limit(BATCH_SIZE)
    )
    event_ids = (await db.execute(stmt)).scalars().all()
    await db.commit()  # release the batch lock

    if not event_ids:
        return 0

    uc = _make_use_cases(db)
    processed = 0
    for eid in event_ids:
        try:
            result = await uc.process_event(eid, system_user_id=_system_user_id())
            # Only count rows this worker actually transitioned to 'processed'.
            # 'skip' / 'not_found' mean another worker already claimed the row
            # (or it was promoted to 'processing' by a concurrent select).
            if result.status == "processed":
                processed += 1
        except Exception as exc:
            # process_event already routes failures through
            # handle_processing_failure, which updates inbound and commits.
            # We only log here so the worker continues with the next event.
            logger.error("inbound_event %s failed: %s", eid, exc)
    return processed


async def _scheduled_retry() -> None:
    from backend.src.core.database import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        n = await retry_pending_events_once(db)
        if n > 0:
            logger.info("inbound_events: %d processed in this batch", n)


def start_inbound_jobs(interval_seconds: int = 5) -> None:
    _scheduler.add_job(
        _scheduled_retry,
        "interval",
        seconds=interval_seconds,
        id="inbound_events_retry",
        replace_existing=True,
    )
    if not _scheduler.running:
        _scheduler.start()


def stop_inbound_jobs() -> None:
    if _scheduler.running:
        _scheduler.shutdown(wait=False)
