from fastapi import APIRouter, Depends

from backend.src.core.dependencies import DBSession
from backend.src.modules.origins.application.use_cases import (
    OriginUseCases,
    OriginResponseDTO,
    CreateOriginDTO,
)
from backend.src.core.responses import SuccessResponse
from backend.src.core.middleware.permission_checker import CurrentUser, PermissionChecker

router = APIRouter(prefix="/api/v1/origins", tags=["origins"])
Manage = Depends(PermissionChecker("cases", "manage"))


@router.get("", response_model=SuccessResponse[list[OriginResponseDTO]])
async def list_origins(
    db: DBSession,
    current_user: CurrentUser = Depends(PermissionChecker("cases", "read")),
):
    uc = OriginUseCases(db)
    return SuccessResponse.ok(await uc.list(current_user.tenant_id))


@router.post("", response_model=SuccessResponse[OriginResponseDTO], status_code=201)
async def create_origin(
    dto: CreateOriginDTO,
    db: DBSession,
    current_user: CurrentUser = Manage,
):
    uc = OriginUseCases(db)
    return SuccessResponse.ok(await uc.create(dto, current_user.tenant_id))


@router.delete("/{origin_id}", status_code=204)
async def deactivate_origin(
    origin_id: str,
    db: DBSession,
    current_user: CurrentUser = Manage,
):
    uc = OriginUseCases(db)
    await uc.deactivate(origin_id)
