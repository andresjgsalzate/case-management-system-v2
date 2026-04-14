from fastapi import APIRouter, Depends

from backend.src.core.dependencies import DBSession
from backend.src.modules.applications.application.use_cases import (
    ApplicationUseCases,
    ApplicationResponseDTO,
    CreateApplicationDTO,
)
from backend.src.core.responses import SuccessResponse
from backend.src.core.middleware.permission_checker import CurrentUser, PermissionChecker

router = APIRouter(prefix="/api/v1/applications", tags=["applications"])
Manage = Depends(PermissionChecker("cases", "manage"))


@router.get("", response_model=SuccessResponse[list[ApplicationResponseDTO]])
async def list_applications(
    db: DBSession,
    current_user: CurrentUser = Depends(PermissionChecker("cases", "read")),
):
    uc = ApplicationUseCases(db)
    return SuccessResponse.ok(await uc.list(current_user.tenant_id))


@router.post("", response_model=SuccessResponse[ApplicationResponseDTO], status_code=201)
async def create_application(
    dto: CreateApplicationDTO,
    db: DBSession,
    current_user: CurrentUser = Manage,
):
    uc = ApplicationUseCases(db)
    return SuccessResponse.ok(await uc.create(dto, current_user.tenant_id))


@router.delete("/{app_id}", status_code=204)
async def deactivate_application(
    app_id: str,
    db: DBSession,
    current_user: CurrentUser = Manage,
):
    uc = ApplicationUseCases(db)
    await uc.deactivate(app_id)


class UpdateApplicationDTO:
    pass

from pydantic import BaseModel as _BM

class _UpdateDTO(_BM):
    name: str | None = None
    description: str | None = None

@router.patch("/{app_id}", response_model=SuccessResponse[ApplicationResponseDTO])
async def update_application(
    app_id: str,
    dto: _UpdateDTO,
    db: DBSession,
    current_user: CurrentUser = Manage,
):
    from sqlalchemy import select
    from backend.src.modules.applications.infrastructure.models import ApplicationModel
    result = await db.execute(select(ApplicationModel).where(ApplicationModel.id == app_id))
    app = result.scalar_one_or_none()
    if not app:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Application not found")
    if dto.name is not None:
        app.name = dto.name
    if dto.description is not None:
        app.description = dto.description
    await db.commit()
    await db.refresh(app)
    return SuccessResponse.ok(ApplicationResponseDTO(
        id=app.id, name=app.name, code=app.code,
        description=app.description, is_active=app.is_active,
    ))
