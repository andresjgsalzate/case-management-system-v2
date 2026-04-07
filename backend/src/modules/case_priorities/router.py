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
