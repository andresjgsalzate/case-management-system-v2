from fastapi import APIRouter, Depends

from backend.src.core.dependencies import DBSession
from backend.src.modules.applications.application.use_cases import (
    ApplicationUseCases,
    ApplicationResponseDTO,
    CreateApplicationDTO,
)
from backend.src.core.responses import SuccessResponse
from backend.src.core.middleware.permission_checker import CurrentUser, PermissionChecker

router = APIRouter(prefix="/api/v1/applications", tags=["applications"])
Manage = Depends(PermissionChecker("cases", "manage"))


@router.get("", response_model=SuccessResponse[list[ApplicationResponseDTO]])
async def list_applications(
    db: DBSession,
    current_user: CurrentUser = Depends(PermissionChecker("cases", "read")),
):
    uc = ApplicationUseCases(db)
    return SuccessResponse.ok(await uc.list(current_user.tenant_id))


@router.post("", response_model=SuccessResponse[ApplicationResponseDTO], status_code=201)
async def create_application(
    dto: CreateApplicationDTO,
    db: DBSession,
    current_user: CurrentUser = Manage,
):
    uc = ApplicationUseCases(db)
    return SuccessResponse.ok(await uc.create(dto, current_user.tenant_id))


@router.delete("/{app_id}", status_code=204)
async def deactivate_application(
    app_id: str,
    db: DBSession,
    current_user: CurrentUser = Manage,
):
    uc = ApplicationUseCases(db)
    await uc.deactivate(app_id)
