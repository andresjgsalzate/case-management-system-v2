import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select, or_
from sqlalchemy.orm import joinedload

from backend.src.core.dependencies import DBSession
from backend.src.modules.sla.infrastructure.models import (
    SLAPolicyModel,
    SLARecordModel,
    SLAHolidayModel,
    SLAWorkScheduleModel,
    SLAIntegrationConfigModel,
)
from backend.src.modules.case_priorities.infrastructure.models import CasePriorityModel
from backend.src.core.middleware.permission_checker import CurrentUser, PermissionChecker
from backend.src.core.responses import SuccessResponse

router = APIRouter(prefix="/api/v1/sla", tags=["sla"])
SLAManage = Depends(PermissionChecker("sla", "manage"))
SLARead = Depends(PermissionChecker("sla", "read"))


class CreatePolicyDTO(BaseModel):
    priority_id: str
    target_resolution_hours: float


class CreateHolidayDTO(BaseModel):
    date: datetime
    description: str
    is_recurring: bool = False


class UpdateWorkScheduleDTO(BaseModel):
    work_days: list[int]
    work_start_time: str
    work_end_time: str


class UpsertIntegrationConfigDTO(BaseModel):
    enabled: bool = False
    pause_on_timer: bool = True
    low_max_hours: float | None = None
    medium_max_hours: float | None = None
    high_max_hours: float | None = None


# ─── Policies ────────────────────────────────────────────────────────────────

@router.get("/policies", response_model=SuccessResponse[list[dict]])
async def list_policies(db: DBSession, current_user: CurrentUser = SLARead):
    result = await db.execute(
        select(SLAPolicyModel, CasePriorityModel)
        .join(CasePriorityModel, SLAPolicyModel.priority_id == CasePriorityModel.id)
        .where(or_(
            SLAPolicyModel.tenant_id == current_user.tenant_id,
            SLAPolicyModel.tenant_id.is_(None),
        ))
    )
    rows = result.all()
    return SuccessResponse.ok([
        {
            "id": p.id,
            "priority_id": p.priority_id,
            "target_resolution_hours": p.target_resolution_hours,
            "priority": {
                "name": pri.name,
                "level": pri.level,
                "color": pri.color,
            },
        }
        for p, pri in rows
    ])


@router.post("/policies", status_code=201)
async def create_policy(
    dto: CreatePolicyDTO, db: DBSession, current_user: CurrentUser = SLAManage
):
    policy = SLAPolicyModel(
        id=str(uuid.uuid4()), tenant_id=current_user.tenant_id, **dto.model_dump()
    )
    db.add(policy)
    await db.commit()
    return SuccessResponse.ok({"id": policy.id})


@router.delete("/policies/{policy_id}", status_code=204)
async def delete_policy(
    policy_id: str, db: DBSession, current_user: CurrentUser = SLAManage
):
    policy = await db.get(SLAPolicyModel, policy_id)
    if policy:
        await db.delete(policy)
        await db.commit()


# ─── Work Schedule ────────────────────────────────────────────────────────────

@router.get("/work-schedule", response_model=SuccessResponse[dict])
async def get_work_schedule(db: DBSession, current_user: CurrentUser = SLARead):
    from backend.src.modules.sla.application.use_cases import get_schedule
    schedule = await get_schedule(db, current_user.tenant_id)
    return SuccessResponse.ok(schedule)


@router.put("/work-schedule")
async def update_work_schedule(
    dto: UpdateWorkScheduleDTO, db: DBSession, current_user: CurrentUser = SLAManage
):
    result = await db.execute(
        select(SLAWorkScheduleModel).where(
            SLAWorkScheduleModel.tenant_id == current_user.tenant_id
        )
    )
    schedule = result.scalar_one_or_none()
    if schedule:
        schedule.work_days = dto.work_days
        schedule.work_start_time = dto.work_start_time
        schedule.work_end_time = dto.work_end_time
    else:
        schedule = SLAWorkScheduleModel(
            id=str(uuid.uuid4()),
            tenant_id=current_user.tenant_id,
            **dto.model_dump(),
        )
        db.add(schedule)
    await db.commit()
    return SuccessResponse.ok({"updated": True})


# ─── Holidays ─────────────────────────────────────────────────────────────────

@router.get("/holidays", response_model=SuccessResponse[list[dict]])
async def list_holidays(db: DBSession, current_user: CurrentUser = SLARead):
    result = await db.execute(
        select(SLAHolidayModel).where(SLAHolidayModel.tenant_id == current_user.tenant_id)
    )
    holidays = result.scalars().all()
    return SuccessResponse.ok([
        {
            "id": h.id,
            "date": h.date.isoformat(),
            "description": h.description,
            "is_recurring": h.is_recurring,
        }
        for h in holidays
    ])


@router.post("/holidays", status_code=201)
async def create_holiday(
    dto: CreateHolidayDTO, db: DBSession, current_user: CurrentUser = SLAManage
):
    holiday = SLAHolidayModel(
        id=str(uuid.uuid4()),
        tenant_id=current_user.tenant_id,
        created_by=current_user.user_id,
        **dto.model_dump(),
    )
    db.add(holiday)
    await db.commit()
    return SuccessResponse.ok({"id": holiday.id})


@router.delete("/holidays/{holiday_id}", status_code=204)
async def delete_holiday(
    holiday_id: str, db: DBSession, current_user: CurrentUser = SLAManage
):
    holiday = await db.get(SLAHolidayModel, holiday_id)
    if holiday:
        await db.delete(holiday)
        await db.commit()


@router.get("/holidays/calendar/{year}", response_model=SuccessResponse[list[dict]])
async def get_holiday_calendar(
    year: int, db: DBSession, current_user: CurrentUser = SLARead
):
    result = await db.execute(
        select(SLAHolidayModel).where(SLAHolidayModel.tenant_id == current_user.tenant_id)
    )
    holidays = result.scalars().all()
    calendar_entries = []
    for h in holidays:
        if h.is_recurring:
            try:
                date_in_year = h.date.replace(year=year)
                calendar_entries.append({
                    "date": date_in_year.date().isoformat(),
                    "description": h.description,
                    "is_recurring": True,
                })
            except ValueError:
                pass
        elif h.date.year == year:
            calendar_entries.append({
                "date": h.date.date().isoformat(),
                "description": h.description,
                "is_recurring": False,
            })
    return SuccessResponse.ok(sorted(calendar_entries, key=lambda x: x["date"]))


# ─── SLA Record (estado actual de un caso) ────────────────────────────────────

@router.get("/records/{case_id}", response_model=SuccessResponse[dict])
async def get_sla_record(
    case_id: str, db: DBSession, current_user: CurrentUser = SLARead
):
    result = await db.execute(
        select(SLARecordModel).where(SLARecordModel.case_id == case_id)
    )
    record = result.scalar_one_or_none()
    if not record:
        return SuccessResponse.ok(None)
    return SuccessResponse.ok({
        "id": record.id,
        "case_id": record.case_id,
        "started_at": record.started_at.isoformat(),
        "target_at": record.target_at.isoformat(),
        "is_breached": record.is_breached,
        "breached_at": record.breached_at.isoformat() if record.breached_at else None,
        "paused_at": record.paused_at.isoformat() if record.paused_at else None,
        "status_paused_at": record.status_paused_at.isoformat() if record.status_paused_at else None,
    })


# ─── Integration Config ───────────────────────────────────────────────────────

@router.get("/integration-config", response_model=SuccessResponse[dict])
async def get_integration_config(db: DBSession, current_user: CurrentUser = SLARead):
    from backend.src.modules.sla.application.use_cases import get_integration_config as _get
    config = await _get(db, current_user.tenant_id)
    return SuccessResponse.ok(config)


@router.put("/integration-config")
async def upsert_integration_config(
    dto: UpsertIntegrationConfigDTO, db: DBSession, current_user: CurrentUser = SLAManage
):
    result = await db.execute(
        select(SLAIntegrationConfigModel).where(
            SLAIntegrationConfigModel.tenant_id == current_user.tenant_id
        )
    )
    config = result.scalar_one_or_none()
    if config:
        config.enabled = dto.enabled
        config.pause_on_timer = dto.pause_on_timer
        config.low_max_hours = dto.low_max_hours
        config.medium_max_hours = dto.medium_max_hours
        config.high_max_hours = dto.high_max_hours
    else:
        config = SLAIntegrationConfigModel(
            id=str(uuid.uuid4()),
            tenant_id=current_user.tenant_id,
            **dto.model_dump(),
        )
        db.add(config)
    await db.commit()
    return SuccessResponse.ok({"updated": True})
