from fastapi import APIRouter, Depends
from backend.src.core.dependencies import DBSession, Pagination
from backend.src.modules.users.application.dtos import (
    CreateUserDTO, UpdateUserDTO, ChangePasswordDTO, UserResponseDTO,
)
from backend.src.modules.users.application.use_cases import UserUseCases
from backend.src.core.responses import SuccessResponse, PaginatedResponse
from backend.src.core.middleware.permission_checker import CurrentUser, PermissionChecker

router = APIRouter(prefix="/users", tags=["users"])
UsersRead = Depends(PermissionChecker("users", "read"))
UsersCreate = Depends(PermissionChecker("users", "create"))
UsersUpdate = Depends(PermissionChecker("users", "update"))


@router.get("", response_model=PaginatedResponse[UserResponseDTO])
async def list_users(
    db: DBSession, pagination: Pagination, current_user: CurrentUser = UsersRead
):
    uc = UserUseCases(db)
    users, total = await uc.list_users(
        current_user.tenant_id, pagination.page, pagination.page_size,
        all_tenants=current_user.is_global,
    )
    return PaginatedResponse.ok(users, total, pagination.page, pagination.page_size)


@router.post("", response_model=SuccessResponse[UserResponseDTO], status_code=201)
async def create_user(
    dto: CreateUserDTO, db: DBSession, current_user: CurrentUser = UsersCreate
):
    uc = UserUseCases(db)
    user = await uc.create_user(dto, current_user.user_id, current_user.tenant_id)
    return SuccessResponse.ok(user)


@router.get("/{user_id}", response_model=SuccessResponse[UserResponseDTO])
async def get_user(user_id: str, db: DBSession, current_user: CurrentUser = UsersRead):
    uc = UserUseCases(db)
    user = await uc.get_user(user_id)
    return SuccessResponse.ok(user)


@router.patch("/{user_id}", response_model=SuccessResponse[UserResponseDTO])
async def update_user(
    user_id: str, dto: UpdateUserDTO, db: DBSession, current_user: CurrentUser = UsersUpdate
):
    uc = UserUseCases(db)
    user = await uc.update_user(user_id, dto, current_user.user_id)
    return SuccessResponse.ok(user)


@router.post("/{user_id}/change-password", status_code=204)
async def change_password(user_id: str, dto: ChangePasswordDTO, db: DBSession):
    uc = UserUseCases(db)
    await uc.change_password(user_id, dto)


@router.post("/{user_id}/deactivate", status_code=204)
async def deactivate_user(
    user_id: str,
    db: DBSession,
    current_user: CurrentUser = Depends(PermissionChecker("users", "delete")),
):
    uc = UserUseCases(db)
    await uc.deactivate_user(user_id, current_user.user_id, current_user.tenant_id)


@router.post("/{user_id}/reactivate", status_code=204)
async def reactivate_user(
    user_id: str,
    db: DBSession,
    current_user: CurrentUser = Depends(PermissionChecker("users", "delete")),
):
    uc = UserUseCases(db)
    await uc.reactivate_user(user_id)
