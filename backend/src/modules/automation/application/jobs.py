import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

logger = logging.getLogger(__name__)
_scheduler = AsyncIOScheduler()


async def _run_scheduled_automations() -> None:
    logger.info("Running scheduled automation jobs...")
    from backend.src.core.database import AsyncSessionLocal
    from backend.src.modules.automation.application.use_cases import AutomationUseCases

    async with AsyncSessionLocal() as db:
        uc = AutomationUseCases(db=db)
        executed = await uc.evaluate_and_execute(
            event_name="schedule.daily",
            context={},
            actor_id="system",
        )
        if executed > 0:
            await db.commit()
        logger.info("Scheduled automations: %d regla(s) ejecutada(s)", executed)


def start_scheduled_automations(interval_hours: int = 24) -> None:
    _scheduler.add_job(
        _run_scheduled_automations,
        "interval",
        hours=interval_hours,
        id="scheduled_automations",
        replace_existing=True,
    )
    if not _scheduler.running:
        _scheduler.start()
    logger.info("Scheduled automations job started (every %dh)", interval_hours)


def stop_scheduled_automations() -> None:
    if _scheduler.running:
        _scheduler.shutdown(wait=False)
