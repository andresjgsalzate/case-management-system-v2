from fastapi import APIRouter, Depends
from pydantic import BaseModel

from backend.src.core.dependencies import DBSession
from backend.src.core.responses import SuccessResponse
from backend.src.core.middleware.permission_checker import CurrentUser, PermissionChecker
from backend.src.modules.dispositions.application.use_cases import DispositionUseCases

router = APIRouter(prefix="/api/v1/dispositions", tags=["dispositions"])
DispRead = Depends(PermissionChecker("dispositions", "read"))
DispCreate = Depends(PermissionChecker("dispositions", "create"))
DispManage = Depends(PermissionChecker("dispositions", "manage"))


class CategoryCreateDTO(BaseModel):
    name: str
    description: str | None = None


class DispositionCreateDTO(BaseModel):
    category_id: str
    title: str
    content: str


class DispositionUpdateDTO(BaseModel):
    title: str | None = None
    content: str | None = None


class ApplyDTO(BaseModel):
    case_id: str


@router.get("/categories", response_model=SuccessResponse[list[dict]])
async def list_categories(
    db: DBSession,
    current_user: CurrentUser = DispRead,
):
    uc = DispositionUseCases(db=db)
    cats = await uc.list_categories(tenant_id=current_user.tenant_id)
    return SuccessResponse.ok([
        {"id": c.id, "name": c.name, "description": c.description, "is_active": c.is_active}
        for c in cats
    ])


@router.post("/categories", status_code=201)
async def create_category(
    body: CategoryCreateDTO,
    db: DBSession,
    current_user: CurrentUser = DispCreate,
):
    uc = DispositionUseCases(db=db)
    cat = await uc.create_category(
        name=body.name,
        description=body.description,
        tenant_id=current_user.tenant_id,
    )
    return SuccessResponse.ok({"id": cat.id, "name": cat.name})


@router.get("", response_model=SuccessResponse[list[dict]])
async def list_dispositions(
    db: DBSession,
    category_id: str | None = None,
    q: str | None = None,
    current_user: CurrentUser = DispRead,
):
    uc = DispositionUseCases(db=db)
    if q:
        items = await uc.search_dispositions(query=q)
    elif category_id:
        items = await uc.list_by_category(category_id=category_id)
    else:
        items = await uc.list_all(tenant_id=current_user.tenant_id)
    return SuccessResponse.ok([
        {
            "id": d.id,
            "category_id": d.category_id,
            "title": d.title,
            "content": d.content,
            "usage_count": d.usage_count,
            "is_active": d.is_active,
        }
        for d in items
    ])


@router.post("", status_code=201)
async def create_disposition(
    body: DispositionCreateDTO,
    db: DBSession,
    current_user: CurrentUser = DispCreate,
):
    uc = DispositionUseCases(db=db)
    disp = await uc.create_disposition(
        category_id=body.category_id,
        title=body.title,
        content=body.content,
        created_by_id=current_user.user_id,
        tenant_id=current_user.tenant_id,
    )
    return SuccessResponse.ok({"id": disp.id, "title": disp.title})


@router.patch("/{disposition_id}")
async def update_disposition(
    disposition_id: str,
    body: DispositionUpdateDTO,
    db: DBSession,
    current_user: CurrentUser = DispCreate,
):
    uc = DispositionUseCases(db=db)
    disp = await uc.update_disposition(
        disposition_id=disposition_id,
        title=body.title,
        content=body.content,
    )
    return SuccessResponse.ok({"id": disp.id, "title": disp.title, "content": disp.content})


@router.post("/{disposition_id}/apply")
async def apply_disposition(
    disposition_id: str,
    body: ApplyDTO,
    db: DBSession,
    current_user: CurrentUser = DispCreate,
):
    uc = DispositionUseCases(db=db)
    disp = await uc.apply_to_case(disposition_id=disposition_id, case_id=body.case_id)
    return SuccessResponse.ok({"id": disp.id, "usage_count": disp.usage_count})


@router.delete("/{disposition_id}", status_code=204)
async def deactivate_disposition(
    disposition_id: str,
    db: DBSession,
    current_user: CurrentUser = DispManage,
):
    uc = DispositionUseCases(db=db)
    await uc.deactivate(disposition_id=disposition_id)
