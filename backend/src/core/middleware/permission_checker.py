from dataclasses import dataclass
from typing import Callable
from fastapi import Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from backend.src.core.database import get_db
from backend.src.core.security import decode_access_token
from backend.src.core.exceptions import UnauthorizedError, PermissionDeniedError
from backend.src.modules.roles.infrastructure.models import PermissionModel

http_bearer = HTTPBearer(auto_error=False)


@dataclass
class CurrentUser:
    user_id: str
    email: str
    role_id: str
    tenant_id: str
    scope: str = "own"


class PermissionChecker:
    """
    FastAPI dependency that verifies the authenticated user has the
    required permission (module, action).

    Usage:
        @router.get("/cases", dependencies=[Depends(PermissionChecker("cases", "read"))])

    Or to get the current user with scope:
        @router.get("/cases")
        async def list_cases(current_user: CurrentUser = Depends(PermissionChecker("cases", "read"))):
    """

    def __init__(self, module: str, action: str):
        self.module = module
        self.action = action

    async def __call__(
        self,
        credentials: HTTPAuthorizationCredentials | None = Depends(http_bearer),
        db: AsyncSession = Depends(get_db),
    ) -> CurrentUser:
        if not credentials:
            raise UnauthorizedError("No authentication token provided")

        payload = decode_access_token(credentials.credentials)
        user_id = payload.get("sub")
        role_id = payload.get("role_id")
        tenant_id = payload.get("tenant_id", "default")
        email = payload.get("email", "")

        if not user_id:
            raise UnauthorizedError("Invalid token payload")

        if not role_id:
            raise PermissionDeniedError("User has no role assigned")

        result = await db.execute(
            select(PermissionModel).where(
                PermissionModel.role_id == role_id,
                PermissionModel.module == self.module,
                PermissionModel.action == self.action,
            )
        )
        permission = result.scalar_one_or_none()

        if not permission:
            raise PermissionDeniedError(
                f"Permission denied: {self.module}.{self.action}"
            )

        return CurrentUser(
            user_id=user_id,
            email=email,
            role_id=role_id,
            tenant_id=tenant_id,
            scope=permission.scope,
        )


def require(module: str, action: str) -> Callable:
    """Shorthand: Depends(require('cases', 'read'))"""
    checker = PermissionChecker(module=module, action=action)
    return Depends(checker)
