from fastapi import APIRouter, Depends

from backend.src.core.dependencies import DBSession
from backend.src.core.responses import SuccessResponse
from backend.src.core.middleware.permission_checker import CurrentUser, PermissionChecker
from backend.src.modules.tenants.application.use_cases import (
    TenantUseCases,
    TenantResponseDTO,
    CreateTenantDTO,
    UpdateTenantDTO,
)

router = APIRouter(prefix="/api/v1/tenants", tags=["tenants"])
Manage = Depends(PermissionChecker("users", "manage"))
Read = Depends(PermissionChecker("users", "read"))


@router.get("", response_model=SuccessResponse[list[TenantResponseDTO]])
async def list_tenants(db: DBSession, current_user: CurrentUser = Read):
    uc = TenantUseCases(db)
    return SuccessResponse.ok(await uc.list())


@router.get("/{tenant_id}", response_model=SuccessResponse[TenantResponseDTO])
async def get_tenant(tenant_id: str, db: DBSession, current_user: CurrentUser = Read):
    uc = TenantUseCases(db)
    return SuccessResponse.ok(await uc.get(tenant_id))


@router.post("", response_model=SuccessResponse[TenantResponseDTO], status_code=201)
async def create_tenant(dto: CreateTenantDTO, db: DBSession, current_user: CurrentUser = Manage):
    uc = TenantUseCases(db)
    return SuccessResponse.ok(await uc.create(dto))


@router.patch("/{tenant_id}", response_model=SuccessResponse[TenantResponseDTO])
async def update_tenant(
    tenant_id: str, dto: UpdateTenantDTO, db: DBSession, current_user: CurrentUser = Manage
):
    uc = TenantUseCases(db)
    return SuccessResponse.ok(await uc.update(tenant_id, dto))


@router.delete("/{tenant_id}", status_code=204)
async def delete_tenant(tenant_id: str, db: DBSession, current_user: CurrentUser = Manage):
    uc = TenantUseCases(db)
    await uc.delete(tenant_id)
