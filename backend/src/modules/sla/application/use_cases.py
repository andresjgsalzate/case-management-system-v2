import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.src.modules.sla.infrastructure.models import (
    SLAPolicyModel,
    SLARecordModel,
    SLAWorkScheduleModel,
    SLAHolidayModel,
)
from backend.src.modules.case_priorities.infrastructure.models import CasePriorityModel
from backend.src.modules.cases.infrastructure.models import CaseModel
from backend.src.modules.sla.application.calculator import calculate_target_at


async def get_schedule(db: AsyncSession, tenant_id: str | None) -> dict:
    result = await db.execute(
        select(SLAWorkScheduleModel).where(SLAWorkScheduleModel.tenant_id == tenant_id)
    )
    schedule_model = result.scalar_one_or_none()
    if schedule_model:
        return {
            "work_days": schedule_model.work_days,
            "work_start_time": schedule_model.work_start_time,
            "work_end_time": schedule_model.work_end_time,
        }
    # Fallback: 24/7 (nunca bloquea el SLA)
    return {"work_days": [0, 1, 2, 3, 4], "work_start_time": "00:00", "work_end_time": "23:59"}


async def get_holidays(db: AsyncSession, tenant_id: str | None) -> list[datetime]:
    result = await db.execute(
        select(SLAHolidayModel).where(SLAHolidayModel.tenant_id == tenant_id)
    )
    holidays = result.scalars().all()
    now = datetime.now(timezone.utc)
    expanded = []
    for h in holidays:
        if h.is_recurring:
            try:
                expanded.append(h.date.replace(year=now.year))
            except ValueError:
                pass  # 29-feb en año no bisiesto
        else:
            expanded.append(h.date)
    return expanded


async def start_sla_for_case(db: AsyncSession, case_id: str, tenant_id: str) -> None:
    case = await db.get(CaseModel, case_id)
    if not case:
        return

    policy_result = await db.execute(
        select(SLAPolicyModel).where(
            SLAPolicyModel.tenant_id == tenant_id,
            SLAPolicyModel.priority_id == case.priority_id,
        )
    )
    policy = policy_result.scalar_one_or_none()
    if not policy:
        return  # Sin política SLA para esta prioridad

    schedule = await get_schedule(db, tenant_id)
    holidays = await get_holidays(db, tenant_id)
    started_at = datetime.now(timezone.utc)
    target_at = calculate_target_at(started_at, policy.target_resolution_hours, schedule, holidays)

    # Upsert: si ya existe un record (ej. reasignación), actualiza
    existing = await db.execute(
        select(SLARecordModel).where(SLARecordModel.case_id == case_id)
    )
    record = existing.scalar_one_or_none()
    if record:
        record.started_at = started_at
        record.target_at = target_at
        record.is_breached = False
        record.breached_at = None
    else:
        record = SLARecordModel(
            id=str(uuid.uuid4()),
            case_id=case_id,
            policy_id=policy.id,
            started_at=started_at,
            target_at=target_at,
        )
        db.add(record)
    await db.commit()


async def check_sla_breaches(db: AsyncSession) -> None:
    """Job periódico: detecta casos con SLA vencido y emite eventos."""
    from backend.src.core.events.bus import event_bus
    from backend.src.core.events.base import BaseEvent

    now = datetime.now(timezone.utc)
    result = await db.execute(
        select(SLARecordModel).where(
            SLARecordModel.is_breached == False,
            SLARecordModel.target_at <= now,
        )
    )
    breached = result.scalars().all()
    for record in breached:
        record.is_breached = True
        record.breached_at = now
        case = await db.get(CaseModel, record.case_id)
        if case and not case.is_archived:
            await event_bus.publish(
                BaseEvent(
                    event_name="sla.breached",
                    tenant_id=case.tenant_id or "default",
                    actor_id="system",
                    payload={"case_id": record.case_id, "case_number": case.case_number},
                )
            )
    if breached:
        await db.commit()
