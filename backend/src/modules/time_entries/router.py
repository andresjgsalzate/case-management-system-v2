from fastapi import APIRouter, Depends
from pydantic import BaseModel

from backend.src.core.dependencies import DBSession
from backend.src.core.responses import SuccessResponse
from backend.src.core.middleware.permission_checker import CurrentUser, PermissionChecker
from backend.src.modules.time_entries.application.use_cases import TimeEntryUseCases

router = APIRouter(prefix="/api/v1", tags=["time_entries"])
TimeRead = Depends(PermissionChecker("time_entries", "read"))
TimeCreate = Depends(PermissionChecker("time_entries", "create"))


class ManualEntryDTO(BaseModel):
    minutes: int
    description: str | None = None


@router.post("/cases/{case_id}/time-entries/timer/start")
async def start_timer(
    case_id: str,
    db: DBSession,
    current_user: CurrentUser = TimeCreate,
):
    uc = TimeEntryUseCases(db=db)
    timer = await uc.start_timer(
        case_id=case_id,
        user_id=current_user.user_id,
        tenant_id=current_user.tenant_id,
    )
    return SuccessResponse.ok({"id": timer.id, "case_id": timer.case_id, "started_at": timer.started_at.isoformat()})


@router.post("/time-entries/timer/stop")
async def stop_timer(
    db: DBSession,
    current_user: CurrentUser = TimeCreate,
):
    uc = TimeEntryUseCases(db=db)
    entry = await uc.stop_timer(user_id=current_user.user_id)
    return SuccessResponse.ok({
        "id": entry.id,
        "case_id": entry.case_id,
        "minutes": entry.minutes,
        "started_at": entry.started_at.isoformat(),
        "stopped_at": entry.stopped_at.isoformat() if entry.stopped_at else None,
    })


@router.post("/cases/{case_id}/time-entries/manual", status_code=201)
async def add_manual_entry(
    case_id: str,
    body: ManualEntryDTO,
    db: DBSession,
    current_user: CurrentUser = TimeCreate,
):
    uc = TimeEntryUseCases(db=db)
    entry = await uc.add_manual(
        case_id=case_id,
        user_id=current_user.user_id,
        tenant_id=current_user.tenant_id,
        minutes=body.minutes,
        description=body.description,
    )
    return SuccessResponse.ok({"id": entry.id, "minutes": entry.minutes})


@router.get("/cases/{case_id}/time-entries", response_model=SuccessResponse[list[dict]])
async def list_time_entries(
    case_id: str,
    db: DBSession,
    current_user: CurrentUser = TimeRead,
):
    uc = TimeEntryUseCases(db=db)
    entries = await uc.list_for_case(case_id)
    total = await uc.get_total_minutes(case_id)
    return SuccessResponse.ok({
        "entries": [
            {
                "id": e.id,
                "entry_type": e.entry_type,
                "minutes": e.minutes,
                "description": e.description,
                "created_at": e.created_at.isoformat(),
            }
            for e in entries
        ],
        "total_minutes": total,
    })


@router.delete("/time-entries/{entry_id}", status_code=204)
async def delete_time_entry(
    entry_id: str,
    db: DBSession,
    current_user: CurrentUser = TimeCreate,
):
    uc = TimeEntryUseCases(db=db)
    await uc.delete_entry(entry_id=entry_id, user_id=current_user.user_id)
