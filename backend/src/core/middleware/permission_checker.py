from dataclasses import dataclass
from typing import Callable

from fastapi import Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.src.core.auth import get_keycloak_validator
from backend.src.core.database import get_db
from backend.src.core.exceptions import UnauthorizedError, PermissionDeniedError
from backend.src.modules.roles.infrastructure.models import PermissionModel, RoleModel

http_bearer = HTTPBearer(auto_error=False)


@dataclass
class CurrentUser:
    user_id: str
    email: str
    role_id: str
    tenant_id: str
    scope: str = "own"
    is_global: bool = False
    role_level: int = 1
    team_id: str | None = None


class PermissionChecker:
    """
    FastAPI dependency that verifies the authenticated user has the
    required permission (module, action).

    As of sub-spec 09 the bearer token is a Keycloak-issued RS256 JWT,
    validated against the realm JWKS. The realm role names from
    `realm_access.roles` are mapped to the highest-`level` matching
    CMS role (so a user with both `admin` and `agent` in their token
    is treated as `admin`).

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

        validator = get_keycloak_validator()
        payload = await validator.validate(credentials.credentials)

        # Resolve the CMS user via email rather than `sub`: Keycloak's
        # POST /admin/realms/{realm}/users silently ignores the supplied
        # `id` field and assigns its own UUID, so `sub` is *not* the same
        # as `users.id` even when migrate_users_to_keycloak sends them.
        # Email is the stable shared identifier and Keycloak's `email`
        # claim comes from the inline mapper on the cms-frontend client.
        email = payload.get("email")
        if not email:
            raise UnauthorizedError("Invalid token payload (missing email)")

        tenant_id = payload.get("tenant_id") or "default"
        realm_roles = payload.get("realm_access", {}).get("roles") or []
        if not realm_roles:
            raise PermissionDeniedError("User has no realm role")

        # Pick the highest-level CMS role that matches a name in the token.
        # Users with multiple realm roles get the most privileged one.
        role_row = (
            await db.execute(
                select(RoleModel)
                .where(RoleModel.name.in_(realm_roles))
                .order_by(RoleModel.level.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if not role_row:
            raise PermissionDeniedError(
                f"No CMS role matches token roles: {realm_roles}"
            )

        permission = (
            await db.execute(
                select(PermissionModel).where(
                    PermissionModel.role_id == role_row.id,
                    PermissionModel.module == self.module,
                    PermissionModel.action == self.action,
                )
            )
        ).scalar_one_or_none()

        if not permission:
            raise PermissionDeniedError(
                f"Permission denied: {self.module}.{self.action}"
            )

        from backend.src.modules.users.infrastructure.models import UserModel
        user_row = (
            await db.execute(
                select(UserModel.id, UserModel.team_id).where(
                    UserModel.email == email
                )
            )
        ).first()
        if not user_row:
            raise UnauthorizedError(
                f"No CMS user provisioned for {email}"
            )
        user_id = user_row.id
        team_id = user_row.team_id

        from backend.src.modules.audit.application.middleware import set_current_actor
        set_current_actor(user_id)

        return CurrentUser(
            user_id=user_id,
            email=email,
            role_id=role_row.id,
            tenant_id=tenant_id,
            scope=permission.scope,
            is_global=bool(role_row.is_global),
            role_level=int(role_row.level),
            team_id=team_id,
        )


def require(module: str, action: str) -> Callable:
    """Shorthand: Depends(require('cases', 'read'))"""
    checker = PermissionChecker(module=module, action=action)
    return Depends(checker)


async def has_permission(
    db: AsyncSession, role_id: str, module: str, action: str
) -> bool:
    """Non-raising permission check. True si el rol tiene (module, action)."""
    result = await db.execute(
        select(PermissionModel).where(
            PermissionModel.role_id == role_id,
            PermissionModel.module == module,
            PermissionModel.action == action,
        )
    )
    return result.scalar_one_or_none() is not None
