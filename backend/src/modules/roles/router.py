from fastapi import APIRouter, Depends
from backend.src.core.dependencies import DBSession
from backend.src.modules.roles.application.dtos import CreateRoleDTO, UpdateRoleDTO, PermissionDTO, RoleResponseDTO
from backend.src.modules.roles.application.use_cases import RoleUseCases
from backend.src.core.responses import SuccessResponse
from backend.src.core.middleware.permission_checker import CurrentUser, PermissionChecker

router = APIRouter(prefix="/roles", tags=["roles"])
RolesRead = Depends(PermissionChecker("roles", "read"))
RolesManage = Depends(PermissionChecker("roles", "manage"))


@router.get("", response_model=SuccessResponse[list[RoleResponseDTO]])
async def list_roles(db: DBSession, current_user: CurrentUser = RolesRead):
    uc = RoleUseCases(db)
    roles = await uc.list_roles()
    return SuccessResponse.ok(roles)


@router.post("", response_model=SuccessResponse[RoleResponseDTO], status_code=201)
async def create_role(dto: CreateRoleDTO, db: DBSession, current_user: CurrentUser = RolesManage):
    uc = RoleUseCases(db)
    role = await uc.create_role(dto)
    return SuccessResponse.ok(role)


@router.get("/{role_id}", response_model=SuccessResponse[RoleResponseDTO])
async def get_role(role_id: str, db: DBSession, current_user: CurrentUser = RolesRead):
    uc = RoleUseCases(db)
    role = await uc.get_role(role_id)
    return SuccessResponse.ok(role)


@router.put("/{role_id}/permissions", response_model=SuccessResponse[RoleResponseDTO])
async def update_permissions(role_id: str, permissions: list[PermissionDTO], db: DBSession, current_user: CurrentUser = RolesManage):
    uc = RoleUseCases(db)
    role = await uc.update_permissions(role_id, permissions)
    return SuccessResponse.ok(role)


@router.patch("/{role_id}", response_model=SuccessResponse[RoleResponseDTO])
async def update_role(role_id: str, dto: UpdateRoleDTO, db: DBSession, current_user: CurrentUser = RolesManage):
    uc = RoleUseCases(db)
    role = await uc.update_role(role_id, dto)
    return SuccessResponse.ok(role)


@router.delete("/{role_id}", status_code=204)
async def delete_role(role_id: str, db: DBSession, current_user: CurrentUser = RolesManage):
    uc = RoleUseCases(db)
    await uc.delete_role(role_id)
