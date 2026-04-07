from typing import Annotated

from fastapi import Depends, Query
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from backend.src.core.database import get_db
from backend.src.core.exceptions import ForbiddenError, UnauthorizedError
from backend.src.core.pagination import PaginationParams
from backend.src.core.security import decode_access_token

security = HTTPBearer()

DbSession = Annotated[AsyncSession, Depends(get_db)]


async def get_current_user_id(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> int:
    payload = decode_access_token(credentials.credentials)
    sub = payload.get("sub")
    if not sub:
        raise UnauthorizedError("Token missing subject claim")
    return int(sub)


CurrentUserId = Annotated[int, Depends(get_current_user_id)]


def require_role(*allowed_roles: str):
    async def _check(
        credentials: HTTPAuthorizationCredentials = Depends(security),
    ) -> int:
        payload = decode_access_token(credentials.credentials)
        role = payload.get("role", "")
        if role not in allowed_roles:
            raise ForbiddenError(
                f"Role '{role}' is not allowed. Required: {list(allowed_roles)}"
            )
        sub = payload.get("sub")
        return int(sub)

    return _check


async def get_pagination(
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
) -> PaginationParams:
    return PaginationParams(page=page, page_size=page_size)


# Phase 1 plan aliases
Pagination = Annotated[PaginationParams, Depends(get_pagination)]
DBSession = DbSession
