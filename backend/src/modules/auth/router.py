from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from backend.src.core.dependencies import DBSession
from backend.src.modules.auth.application.dtos import LoginDTO, RefreshDTO, TokenResponseDTO
from backend.src.modules.auth.application.use_cases import AuthUseCases
from backend.src.core.responses import SuccessResponse
from backend.src.core.security import decode_access_token
from backend.src.core.exceptions import UnauthorizedError

_bearer = HTTPBearer(auto_error=False)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=SuccessResponse[TokenResponseDTO])
async def login(dto: LoginDTO, request: Request, db: DBSession):
    uc = AuthUseCases(db)
    tokens = await uc.login(dto, ip_address=request.client.host if request.client else None)
    return SuccessResponse.ok(tokens)


@router.post("/refresh", response_model=SuccessResponse[TokenResponseDTO])
async def refresh(dto: RefreshDTO, db: DBSession):
    uc = AuthUseCases(db)
    tokens = await uc.refresh(dto.refresh_token)
    return SuccessResponse.ok(tokens)


@router.post("/logout", status_code=204)
async def logout(dto: RefreshDTO, db: DBSession):
    uc = AuthUseCases(db)
    await uc.logout(dto.refresh_token)


@router.get("/me")
async def get_me(
    db: DBSession,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
):
    if not credentials:
        raise HTTPException(status_code=401, detail="Not authenticated")
    payload = decode_access_token(credentials.credentials)
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token")
    from sqlalchemy import select
    from backend.src.modules.users.infrastructure.models import UserModel
    result = await db.execute(select(UserModel).where(UserModel.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    from sqlalchemy import select as sa_select
    from backend.src.modules.roles.infrastructure.models import RoleModel, PermissionModel

    role_name = None
    permissions: list[dict] = []
    if user.role_id:
        role_result = await db.execute(sa_select(RoleModel).where(RoleModel.id == user.role_id))
        role = role_result.scalar_one_or_none()
        if role:
            role_name = role.name
        perm_result = await db.execute(
            sa_select(PermissionModel).where(PermissionModel.role_id == user.role_id)
        )
        permissions = [
            {"module": p.module, "action": p.action, "scope": p.scope}
            for p in perm_result.scalars().all()
        ]

    return SuccessResponse.ok({
        "id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "role_id": user.role_id,
        "role_name": role_name,
        "permissions": permissions,
        "is_active": user.is_active,
        "avatar_url": getattr(user, "avatar_url", None),
        "email_notifications": getattr(user, "email_notifications", False),
        "created_at": user.created_at.isoformat() if user.created_at else "",
        "updated_at": user.updated_at.isoformat() if user.updated_at else "",
    })
