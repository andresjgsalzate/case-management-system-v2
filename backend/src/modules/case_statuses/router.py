from fastapi import APIRouter, Depends

from backend.src.core.dependencies import DBSession
from backend.src.modules.case_statuses.application.dtos import (
    CreateCaseStatusDTO,
    CaseStatusResponseDTO,
)
from backend.src.modules.case_statuses.application.use_cases import CaseStatusUseCases
from backend.src.core.responses import SuccessResponse
from backend.src.core.middleware.permission_checker import CurrentUser, PermissionChecker

router = APIRouter(prefix="/api/v1/case-statuses", tags=["case-statuses"])
Manage = Depends(PermissionChecker("cases", "manage"))


@router.get("", response_model=SuccessResponse[list[CaseStatusResponseDTO]])
async def list_statuses(
    db: DBSession,
    current_user: CurrentUser = Depends(PermissionChecker("cases", "read")),
):
    uc = CaseStatusUseCases(db)
    return SuccessResponse.ok(await uc.list_statuses(current_user.tenant_id))


@router.post("", response_model=SuccessResponse[CaseStatusResponseDTO], status_code=201)
async def create_status(
    dto: CreateCaseStatusDTO,
    db: DBSession,
    current_user: CurrentUser = Manage,
):
    uc = CaseStatusUseCases(db)
    return SuccessResponse.ok(await uc.create_status(dto, current_user.tenant_id))


@router.delete("/{status_id}", status_code=204)
async def delete_status(
    status_id: str,
    db: DBSession,
    current_user: CurrentUser = Manage,
):
    uc = CaseStatusUseCases(db)
    await uc.delete_status(status_id)


from pydantic import BaseModel as _BM

class _UpdateStatusDTO(_BM):
    name: str | None = None
    color: str | None = None
    order: int | None = None
    is_initial: bool | None = None
    is_final: bool | None = None
    pauses_sla: bool | None = None
    allowed_transitions: list[str] | None = None

@router.patch("/{status_id}", response_model=SuccessResponse[CaseStatusResponseDTO])
async def update_status(
    status_id: str,
    dto: _UpdateStatusDTO,
    db: DBSession,
    current_user: CurrentUser = Manage,
):
    from sqlalchemy import select
    from backend.src.modules.case_statuses.infrastructure.models import CaseStatusModel
    result = await db.execute(select(CaseStatusModel).where(CaseStatusModel.id == status_id))
    s = result.scalar_one_or_none()
    if not s:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Status not found")
    if dto.name is not None: s.name = dto.name
    if dto.color is not None: s.color = dto.color
    if dto.order is not None: s.order = dto.order
    if dto.is_initial is not None: s.is_initial = dto.is_initial
    if dto.is_final is not None: s.is_final = dto.is_final
    if dto.pauses_sla is not None: s.pauses_sla = dto.pauses_sla
    if dto.allowed_transitions is not None: s.allowed_transitions = dto.allowed_transitions
    await db.commit()
    await db.refresh(s)
    uc = CaseStatusUseCases(db)
    return SuccessResponse.ok(uc._to_dto(s))
