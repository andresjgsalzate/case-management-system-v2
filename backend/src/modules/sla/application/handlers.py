from datetime import datetime, timezone

from backend.src.core.events.base import BaseEvent


async def handle_case_created_for_sla(event: BaseEvent) -> None:
    case_id = event.payload.get("case_id")
    if not case_id:
        return
    from backend.src.core.database import AsyncSessionLocal
    from backend.src.modules.sla.application.use_cases import start_sla_for_case

    async with AsyncSessionLocal() as db:
        await start_sla_for_case(db, case_id, event.tenant_id)


async def handle_timer_started(event: BaseEvent) -> None:
    """Pauses SLA for the case when an agent starts a timer (if integration enabled)."""
    case_id = event.payload.get("case_id")
    if not case_id:
        return
    from backend.src.core.database import AsyncSessionLocal
    from backend.src.modules.sla.infrastructure.models import SLARecordModel, SLAIntegrationConfigModel
    from sqlalchemy import select

    async with AsyncSessionLocal() as db:
        cfg_result = await db.execute(
            select(SLAIntegrationConfigModel).where(
                SLAIntegrationConfigModel.tenant_id == event.tenant_id
            )
        )
        config = cfg_result.scalar_one_or_none()
        if not config or not config.enabled or not config.pause_on_timer:
            return

        record_result = await db.execute(
            select(SLARecordModel).where(SLARecordModel.case_id == case_id)
        )
        record = record_result.scalar_one_or_none()
        if not record or record.is_breached or record.paused_at is not None:
            return

        record.paused_at = datetime.now(timezone.utc)
        await db.commit()


async def handle_timer_stopped(event: BaseEvent) -> None:
    """Resumes SLA and extends target_at by the paused duration."""
    case_id = event.payload.get("case_id")
    if not case_id:
        return
    from backend.src.core.database import AsyncSessionLocal
    from backend.src.modules.sla.infrastructure.models import SLARecordModel, SLAIntegrationConfigModel
    from backend.src.modules.sla.application.use_cases import recalculate_target_at
    from sqlalchemy import select

    async with AsyncSessionLocal() as db:
        cfg_result = await db.execute(
            select(SLAIntegrationConfigModel).where(
                SLAIntegrationConfigModel.tenant_id == event.tenant_id
            )
        )
        config = cfg_result.scalar_one_or_none()
        if not config or not config.enabled or not config.pause_on_timer:
            return

        record_result = await db.execute(
            select(SLARecordModel).where(SLARecordModel.case_id == case_id)
        )
        record = record_result.scalar_one_or_none()
        if not record or record.paused_at is None:
            return

        now = datetime.now(timezone.utc)
        paused_at = record.paused_at
        if paused_at.tzinfo is None:
            paused_at = paused_at.replace(tzinfo=timezone.utc)

        paused_seconds = int((now - paused_at).total_seconds())
        record.total_paused_seconds = (record.total_paused_seconds or 0) + paused_seconds
        record.paused_at = None

        await recalculate_target_at(db, record)
        await db.commit()


async def handle_manual_time_added(event: BaseEvent) -> None:
    """Extends SLA target_at by the manual minutes when the deadline is today."""
    case_id = event.payload.get("case_id")
    minutes = event.payload.get("minutes", 0)
    if not case_id or not minutes:
        return
    from backend.src.core.database import AsyncSessionLocal
    from backend.src.modules.sla.infrastructure.models import SLARecordModel, SLAIntegrationConfigModel
    from sqlalchemy import select
    from datetime import timedelta

    async with AsyncSessionLocal() as db:
        cfg_result = await db.execute(
            select(SLAIntegrationConfigModel).where(
                SLAIntegrationConfigModel.tenant_id == event.tenant_id
            )
        )
        config = cfg_result.scalar_one_or_none()
        if not config or not config.enabled:
            return

        record_result = await db.execute(
            select(SLARecordModel).where(SLARecordModel.case_id == case_id)
        )
        record = record_result.scalar_one_or_none()
        if not record or record.is_breached:
            return

        now = datetime.now(timezone.utc)
        target_date = record.target_at
        if target_date.tzinfo is None:
            target_date = target_date.replace(tzinfo=timezone.utc)

        # Only extend if deadline falls today (UTC)
        if target_date.date() == now.date():
            record.target_at = target_date + timedelta(minutes=minutes)
            await db.commit()


async def handle_status_changed_for_sla(event: BaseEvent) -> None:
    """Pausa o reanuda el SLA según si el nuevo estado tiene pauses_sla=True."""
    case_id = event.payload.get("case_id")
    to_status_id = event.payload.get("to_status_id")
    if not case_id or not to_status_id:
        return

    from backend.src.core.database import AsyncSessionLocal
    from backend.src.modules.sla.infrastructure.models import SLARecordModel
    from backend.src.modules.sla.application.use_cases import recalculate_target_at
    from backend.src.modules.case_statuses.infrastructure.models import CaseStatusModel
    from sqlalchemy import select

    async with AsyncSessionLocal() as db:
        target_status = await db.get(CaseStatusModel, to_status_id)
        if not target_status:
            return

        record_result = await db.execute(
            select(SLARecordModel).where(SLARecordModel.case_id == case_id)
        )
        record = record_result.scalar_one_or_none()
        if not record or record.is_breached:
            return

        now = datetime.now(timezone.utc)

        if target_status.pauses_sla:
            # Pausar por estado solo si no está ya pausado por estado
            if record.status_paused_at is None:
                record.status_paused_at = now
                await db.commit()
        else:
            # Reanudar pausa por estado si estaba pausado
            if record.status_paused_at is not None:
                paused_at = record.status_paused_at
                if paused_at.tzinfo is None:
                    paused_at = paused_at.replace(tzinfo=timezone.utc)
                paused_seconds = int((now - paused_at).total_seconds())
                record.total_paused_seconds = (record.total_paused_seconds or 0) + paused_seconds
                record.status_paused_at = None
                await recalculate_target_at(db, record)
                await db.commit()


def register_handlers(bus) -> None:
    bus.subscribe("case.created", handle_case_created_for_sla)
    bus.subscribe("case.assigned", handle_case_created_for_sla)
    bus.subscribe("timer.started", handle_timer_started)
    bus.subscribe("timer.stopped", handle_timer_stopped)
    bus.subscribe("time_entry.manual_added", handle_manual_time_added)
    bus.subscribe("case.status_changed", handle_status_changed_for_sla)
