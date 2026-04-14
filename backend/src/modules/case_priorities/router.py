from fastapi import APIRouter, Depends

from backend.src.core.dependencies import DBSession
from backend.src.modules.case_priorities.application.dtos import (
    CreateCasePriorityDTO,
    CasePriorityResponseDTO,
)
from backend.src.modules.case_priorities.application.use_cases import CasePriorityUseCases
from backend.src.core.responses import SuccessResponse
from backend.src.core.middleware.permission_checker import CurrentUser, PermissionChecker

router = APIRouter(prefix="/api/v1/case-priorities", tags=["case-priorities"])
Manage = Depends(PermissionChecker("cases", "manage"))


@router.get("", response_model=SuccessResponse[list[CasePriorityResponseDTO]])
async def list_priorities(
    db: DBSession,
    current_user: CurrentUser = Depends(PermissionChecker("cases", "read")),
):
    uc = CasePriorityUseCases(db)
    return SuccessResponse.ok(await uc.list_priorities(current_user.tenant_id))


@router.post("", response_model=SuccessResponse[CasePriorityResponseDTO], status_code=201)
async def create_priority(
    dto: CreateCasePriorityDTO,
    db: DBSession,
    current_user: CurrentUser = Manage,
):
    uc = CasePriorityUseCases(db)
    return SuccessResponse.ok(await uc.create_priority(dto, current_user.tenant_id))


@router.delete("/{priority_id}", status_code=204)
async def deactivate_priority(
    priority_id: str,
    db: DBSession,
    current_user: CurrentUser = Manage,
):
    uc = CasePriorityUseCases(db)
    await uc.deactivate_priority(priority_id)


from pydantic import BaseModel as _BM

class _UpdatePriorityDTO(_BM):
    name: str | None = None
    color: str | None = None
    level: int | None = None
    is_default: bool | None = None

@router.patch("/{priority_id}", response_model=SuccessResponse[CasePriorityResponseDTO])
async def update_priority(
    priority_id: str,
    dto: _UpdatePriorityDTO,
    db: DBSession,
    current_user: CurrentUser = Manage,
):
    from sqlalchemy import select
    from backend.src.modules.case_priorities.infrastructure.models import CasePriorityModel
    result = await db.execute(select(CasePriorityModel).where(CasePriorityModel.id == priority_id))
    p = result.scalar_one_or_none()
    if not p:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Priority not found")
    if dto.name is not None: p.name = dto.name
    if dto.color is not None: p.color = dto.color
    if dto.level is not None: p.level = dto.level
    if dto.is_default is not None: p.is_default = dto.is_default
    await db.commit()
    await db.refresh(p)
    uc = CasePriorityUseCases(db)
    return SuccessResponse.ok(uc._to_dto(p))
