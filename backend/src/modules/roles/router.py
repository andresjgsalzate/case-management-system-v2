from fastapi import APIRouter
from backend.src.core.dependencies import DBSession
from backend.src.modules.roles.application.dtos import CreateRoleDTO, PermissionDTO, RoleResponseDTO
from backend.src.modules.roles.application.use_cases import RoleUseCases
from backend.src.core.responses import SuccessResponse

router = APIRouter(prefix="/roles", tags=["roles"])


@router.get("", response_model=SuccessResponse[list[RoleResponseDTO]])
async def list_roles(db: DBSession):
    uc = RoleUseCases(db)
    roles = await uc.list_roles()
    return SuccessResponse.ok(roles)


@router.post("", response_model=SuccessResponse[RoleResponseDTO], status_code=201)
async def create_role(dto: CreateRoleDTO, db: DBSession):
    uc = RoleUseCases(db)
    role = await uc.create_role(dto)
    return SuccessResponse.ok(role)


@router.get("/{role_id}", response_model=SuccessResponse[RoleResponseDTO])
async def get_role(role_id: str, db: DBSession):
    uc = RoleUseCases(db)
    role = await uc.get_role(role_id)
    return SuccessResponse.ok(role)


@router.put("/{role_id}/permissions", response_model=SuccessResponse[RoleResponseDTO])
async def update_permissions(role_id: str, permissions: list[PermissionDTO], db: DBSession):
    uc = RoleUseCases(db)
    role = await uc.update_permissions(role_id, permissions)
    return SuccessResponse.ok(role)


@router.delete("/{role_id}", status_code=204)
async def delete_role(role_id: str, db: DBSession):
    uc = RoleUseCases(db)
    await uc.delete_role(role_id)
