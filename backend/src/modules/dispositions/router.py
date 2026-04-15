from datetime import date as DateType

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


# ── DTOs ──────────────────────────────────────────────────────────────────────

class CategoryCreateDTO(BaseModel):
    name: str
    description: str | None = None


class DispositionCreateDTO(BaseModel):
    category_id: str
    date: DateType | None = None
    case_number: str | None = None
    item_name: str | None = None
    storage_path: str | None = None
    revision_number: str | None = None
    observations: str | None = None
    # Legacy
    title: str | None = None
    content: str | None = None


class DispositionUpdateDTO(BaseModel):
    category_id: str | None = None
    date: DateType | None = None
    case_number: str | None = None
    item_name: str | None = None
    storage_path: str | None = None
    revision_number: str | None = None
    observations: str | None = None
    title: str | None = None
    content: str | None = None


# ── Category endpoints ────────────────────────────────────────────────────────

@router.get("/categories", response_model=SuccessResponse[list[dict]])
async def list_categories(db: DBSession, current_user: CurrentUser = DispRead):
    uc = DispositionUseCases(db=db)
    cats = await uc.list_categories(tenant_id=current_user.tenant_id)
    return SuccessResponse.ok([
        {"id": c.id, "name": c.name, "description": c.description, "is_active": c.is_active}
        for c in cats
    ])


@router.post("/categories", status_code=201)
async def create_category(body: CategoryCreateDTO, db: DBSession, current_user: CurrentUser = DispCreate):
    uc = DispositionUseCases(db=db)
    cat = await uc.create_category(name=body.name, description=body.description, tenant_id=current_user.tenant_id)
    return SuccessResponse.ok({"id": cat.id, "name": cat.name})


# ── Summary / grouped view ────────────────────────────────────────────────────

@router.get("/summary", response_model=SuccessResponse[list[dict]])
async def get_cases_summary(db: DBSession, current_user: CurrentUser = DispRead):
    uc = DispositionUseCases(db=db)
    summary = await uc.get_cases_summary(tenant_id=current_user.tenant_id)
    return SuccessResponse.ok(summary)


# ── Disposition list / create ─────────────────────────────────────────────────

@router.get("", response_model=SuccessResponse[list[dict]])
async def list_dispositions(
    db: DBSession,
    category_id: str | None = None,
    case_number: str | None = None,
    q: str | None = None,
    current_user: CurrentUser = DispRead,
):
    uc = DispositionUseCases(db=db)
    if q:
        items = await uc.search_dispositions(query=q)
    elif case_number:
        items = await uc.list_by_case_number(case_number=case_number)
    elif category_id:
        items = await uc.list_by_category(category_id=category_id)
    else:
        items = await uc.list_all(tenant_id=current_user.tenant_id)
    return SuccessResponse.ok([_serialize(d) for d in items])


@router.post("", status_code=201)
async def create_disposition(body: DispositionCreateDTO, db: DBSession, current_user: CurrentUser = DispCreate):
    uc = DispositionUseCases(db=db)
    disp = await uc.create_disposition(
        category_id=body.category_id,
        disp_date=body.date,
        case_number=body.case_number,
        item_name=body.item_name,
        storage_path=body.storage_path,
        revision_number=body.revision_number,
        observations=body.observations,
        title=body.title,
        content=body.content,
        created_by_id=current_user.user_id,
        tenant_id=current_user.tenant_id,
    )
    return SuccessResponse.ok(_serialize(disp))


# ── Disposition detail / update / delete ──────────────────────────────────────

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
        category_id=body.category_id,
        disp_date=body.date,
        case_number=body.case_number,
        item_name=body.item_name,
        storage_path=body.storage_path,
        revision_number=body.revision_number,
        observations=body.observations,
        title=body.title,
        content=body.content,
    )
    return SuccessResponse.ok(_serialize(disp))


@router.delete("/{disposition_id}", status_code=204)
async def deactivate_disposition(disposition_id: str, db: DBSession, current_user: CurrentUser = DispManage):
    uc = DispositionUseCases(db=db)
    await uc.deactivate(disposition_id=disposition_id)


# ── Legacy apply endpoint ─────────────────────────────────────────────────────

@router.post("/{disposition_id}/apply")
async def apply_disposition(
    disposition_id: str,
    db: DBSession,
    current_user: CurrentUser = DispCreate,
):
    uc = DispositionUseCases(db=db)
    disp = await uc.apply_to_case(disposition_id=disposition_id, case_id="")
    return SuccessResponse.ok({"id": disp.id, "usage_count": disp.usage_count})


# ── Serializer ────────────────────────────────────────────────────────────────

def _serialize(d) -> dict:
    return {
        "id": d.id,
        "category_id": d.category_id,
        "date": d.date.isoformat() if d.date else None,
        "case_number": d.case_number,
        "item_name": d.item_name,
        "storage_path": d.storage_path,
        "revision_number": d.revision_number,
        "observations": d.observations,
        "title": d.title,
        "content": d.content,
        "usage_count": d.usage_count,
        "is_active": d.is_active,
        "created_at": d.created_at.isoformat(),
        "updated_at": d.updated_at.isoformat(),
    }
