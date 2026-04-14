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


from pydantic import BaseModel as _BM

class _UpdateOriginDTO(_BM):
    name: str | None = None
    code: str | None = None

@router.patch("/{origin_id}", response_model=SuccessResponse[OriginResponseDTO])
async def update_origin(
    origin_id: str,
    dto: _UpdateOriginDTO,
    db: DBSession,
    current_user: CurrentUser = Manage,
):
    from sqlalchemy import select
    from backend.src.modules.origins.infrastructure.models import OriginModel
    result = await db.execute(select(OriginModel).where(OriginModel.id == origin_id))
    o = result.scalar_one_or_none()
    if not o:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Origin not found")
    if dto.name is not None: o.name = dto.name
    if dto.code is not None: o.code = dto.code.upper()
    await db.commit()
    await db.refresh(o)
    return SuccessResponse.ok(OriginResponseDTO(id=o.id, name=o.name, code=o.code, is_active=o.is_active))
