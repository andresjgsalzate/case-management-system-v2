import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

logger = logging.getLogger(__name__)
_scheduler = AsyncIOScheduler()


async def _run_sla_check() -> None:
    logger.info("Running SLA breach check...")
    from backend.src.core.database import AsyncSessionLocal
    from backend.src.modules.sla.application.use_cases import check_sla_breaches

    async with AsyncSessionLocal() as db:
        await check_sla_breaches(db)


def start_sla_scheduler(interval_minutes: int = 5) -> None:
    _scheduler.add_job(
        _run_sla_check,
        "interval",
        minutes=interval_minutes,
        id="sla_breach_check",
        replace_existing=True,
    )
    if not _scheduler.running:
        _scheduler.start()
    logger.info(f"SLA scheduler started (every {interval_minutes} minutes)")


def stop_sla_scheduler() -> None:
    if _scheduler.running:
        _scheduler.shutdown(wait=False)
