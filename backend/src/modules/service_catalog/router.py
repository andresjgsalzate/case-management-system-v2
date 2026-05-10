from fastapi import APIRouter, Depends, Query

from backend.src.core.dependencies import DBSession
from backend.src.core.middleware.permission_checker import CurrentUser, PermissionChecker
from backend.src.core.responses import SuccessResponse
from backend.src.modules.service_catalog.application.dtos import (
    CategoryResponseDTO,
    CreateCategoryDTO,
    CreateFieldDTO,
    CreateItemDTO,
    FieldResponseDTO,
    ItemResponseDTO,
    ReorderFieldsDTO,
    UpdateCategoryDTO,
    UpdateFieldDTO,
    UpdateItemDTO,
)
from backend.src.modules.service_catalog.application.use_cases import (
    CategoryUseCases,
    FieldUseCases,
    ItemUseCases,
)

router = APIRouter(prefix="/api/v1/service-catalog", tags=["service-catalog"])

ReadPerm = Depends(PermissionChecker("service_catalog", "read"))
CreatePerm = Depends(PermissionChecker("service_catalog", "create"))
UpdatePerm = Depends(PermissionChecker("service_catalog", "update"))
DeletePerm = Depends(PermissionChecker("service_catalog", "delete"))


# ── Categories ────────────────────────────────────────────────────────────────


@router.get("/categories", response_model=SuccessResponse[list[CategoryResponseDTO]])
async def list_categories(
    db: DBSession,
    current_user: CurrentUser = ReadPerm,
):
    uc = CategoryUseCases(db)
    return SuccessResponse.ok(await uc.list(current_user.tenant_id))


@router.post(
    "/categories",
    response_model=SuccessResponse[CategoryResponseDTO],
    status_code=201,
)
async def create_category(
    dto: CreateCategoryDTO,
    db: DBSession,
    current_user: CurrentUser = CreatePerm,
):
    uc = CategoryUseCases(db)
    return SuccessResponse.ok(await uc.create(dto, current_user.tenant_id))


@router.patch(
    "/categories/{category_id}",
    response_model=SuccessResponse[CategoryResponseDTO],
)
async def update_category(
    category_id: str,
    dto: UpdateCategoryDTO,
    db: DBSession,
    current_user: CurrentUser = UpdatePerm,
):
    uc = CategoryUseCases(db)
    return SuccessResponse.ok(await uc.update(category_id, dto))


@router.delete("/categories/{category_id}", status_code=204)
async def delete_category(
    category_id: str,
    db: DBSession,
    current_user: CurrentUser = DeletePerm,
):
    uc = CategoryUseCases(db)
    await uc.delete(category_id)


# ── Items ─────────────────────────────────────────────────────────────────────


@router.get("/items", response_model=SuccessResponse[list[ItemResponseDTO]])
async def list_items(
    db: DBSession,
    category_id: str | None = Query(default=None),
    current_user: CurrentUser = ReadPerm,
):
    uc = ItemUseCases(db)
    return SuccessResponse.ok(await uc.list(current_user.tenant_id, category_id))


@router.get("/items/{item_id}", response_model=SuccessResponse[ItemResponseDTO])
async def get_item(
    item_id: str,
    db: DBSession,
    current_user: CurrentUser = ReadPerm,
):
    uc = ItemUseCases(db)
    return SuccessResponse.ok(await uc.get(item_id))


@router.post(
    "/items", response_model=SuccessResponse[ItemResponseDTO], status_code=201
)
async def create_item(
    dto: CreateItemDTO,
    db: DBSession,
    current_user: CurrentUser = CreatePerm,
):
    uc = ItemUseCases(db)
    return SuccessResponse.ok(await uc.create(dto, current_user.tenant_id))


@router.patch(
    "/items/{item_id}", response_model=SuccessResponse[ItemResponseDTO]
)
async def update_item(
    item_id: str,
    dto: UpdateItemDTO,
    db: DBSession,
    current_user: CurrentUser = UpdatePerm,
):
    uc = ItemUseCases(db)
    return SuccessResponse.ok(await uc.update(item_id, dto))


@router.delete("/items/{item_id}", status_code=204)
async def delete_item(
    item_id: str,
    db: DBSession,
    current_user: CurrentUser = DeletePerm,
):
    uc = ItemUseCases(db)
    await uc.delete(item_id)


# ── Fields ────────────────────────────────────────────────────────────────────


@router.get(
    "/items/{item_id}/fields",
    response_model=SuccessResponse[list[FieldResponseDTO]],
)
async def list_item_fields(
    item_id: str,
    db: DBSession,
    current_user: CurrentUser = ReadPerm,
):
    uc = FieldUseCases(db)
    return SuccessResponse.ok(await uc.list_for_item(item_id))


@router.post(
    "/fields",
    response_model=SuccessResponse[FieldResponseDTO],
    status_code=201,
)
async def create_field(
    dto: CreateFieldDTO,
    db: DBSession,
    current_user: CurrentUser = CreatePerm,
):
    uc = FieldUseCases(db)
    return SuccessResponse.ok(await uc.create(dto, current_user.tenant_id))


@router.patch(
    "/fields/{field_id}",
    response_model=SuccessResponse[FieldResponseDTO],
)
async def update_field(
    field_id: str,
    dto: UpdateFieldDTO,
    db: DBSession,
    current_user: CurrentUser = UpdatePerm,
):
    uc = FieldUseCases(db)
    return SuccessResponse.ok(await uc.update(field_id, dto))


@router.delete("/fields/{field_id}", status_code=204)
async def delete_field(
    field_id: str,
    db: DBSession,
    current_user: CurrentUser = DeletePerm,
):
    uc = FieldUseCases(db)
    await uc.delete(field_id)


@router.post(
    "/items/{item_id}/fields/reorder",
    response_model=SuccessResponse[list[FieldResponseDTO]],
)
async def reorder_fields(
    item_id: str,
    dto: ReorderFieldsDTO,
    db: DBSession,
    current_user: CurrentUser = UpdatePerm,
):
    uc = FieldUseCases(db)
    return SuccessResponse.ok(await uc.reorder(item_id, dto))
