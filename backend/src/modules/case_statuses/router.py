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
