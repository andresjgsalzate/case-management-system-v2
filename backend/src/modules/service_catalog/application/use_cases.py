import json
import re
import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.src.core.exceptions import ConflictError, NotFoundError, ValidationError
from backend.src.core.tenant import catalog_filter
from backend.src.modules.service_catalog.application.dtos import (
    CaseCustomValueDTO,
    CaseCustomValueResponseDTO,
    CategoryResponseDTO,
    CreateCategoryDTO,
    CreateFieldDTO,
    CreateItemDTO,
    FieldOption,
    FieldResponseDTO,
    ItemResponseDTO,
    ReorderFieldsDTO,
    UpdateCategoryDTO,
    UpdateFieldDTO,
    UpdateItemDTO,
)
from backend.src.modules.service_catalog.infrastructure.models import (
    CaseCustomValueModel,
    ServiceCatalogCategoryModel,
    ServiceCatalogFieldModel,
    ServiceCatalogItemModel,
)


# ── Categories ────────────────────────────────────────────────────────────────


class CategoryUseCases:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list(self, tenant_id: str | None) -> list[CategoryResponseDTO]:
        item_count_subq = (
            select(
                ServiceCatalogItemModel.category_id,
                func.count(ServiceCatalogItemModel.id).label("cnt"),
            )
            .where(ServiceCatalogItemModel.is_active == True)
            .group_by(ServiceCatalogItemModel.category_id)
            .subquery()
        )
        result = await self.db.execute(
            select(ServiceCatalogCategoryModel, item_count_subq.c.cnt)
            .outerjoin(
                item_count_subq,
                item_count_subq.c.category_id == ServiceCatalogCategoryModel.id,
            )
            .where(catalog_filter(ServiceCatalogCategoryModel, tenant_id))
            .order_by(ServiceCatalogCategoryModel.sort_order.asc(), ServiceCatalogCategoryModel.name.asc())
        )
        out: list[CategoryResponseDTO] = []
        for cat, cnt in result.all():
            out.append(
                CategoryResponseDTO(
                    id=cat.id,
                    name=cat.name,
                    slug=cat.slug,
                    description=cat.description,
                    icon=cat.icon,
                    color=cat.color,
                    is_active=cat.is_active,
                    sort_order=cat.sort_order,
                    item_count=cnt or 0,
                )
            )
        return out

    async def create(
        self, dto: CreateCategoryDTO, tenant_id: str | None
    ) -> CategoryResponseDTO:
        existing = await self.db.execute(
            select(ServiceCatalogCategoryModel).where(
                ServiceCatalogCategoryModel.tenant_id == tenant_id,
                ServiceCatalogCategoryModel.slug == dto.slug,
            )
        )
        if existing.scalar_one_or_none():
            raise ConflictError(f"Category slug '{dto.slug}' already exists")
        cat = ServiceCatalogCategoryModel(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            name=dto.name,
            slug=dto.slug,
            description=dto.description,
            icon=dto.icon,
            color=dto.color,
            sort_order=dto.sort_order,
        )
        self.db.add(cat)
        await self.db.commit()
        await self.db.refresh(cat)
        return _category_to_dto(cat, item_count=0)

    async def update(
        self, category_id: str, dto: UpdateCategoryDTO
    ) -> CategoryResponseDTO:
        cat = await self.db.get(ServiceCatalogCategoryModel, category_id)
        if not cat:
            raise NotFoundError(f"Category {category_id} not found")
        for field, value in dto.model_dump(exclude_none=True).items():
            setattr(cat, field, value)
        await self.db.commit()
        await self.db.refresh(cat)
        return _category_to_dto(cat, item_count=0)

    async def delete(self, category_id: str) -> None:
        cat = await self.db.get(ServiceCatalogCategoryModel, category_id)
        if not cat:
            raise NotFoundError(f"Category {category_id} not found")
        items = await self.db.execute(
            select(ServiceCatalogItemModel.id)
            .where(ServiceCatalogItemModel.category_id == category_id)
            .limit(1)
        )
        if items.scalar_one_or_none():
            raise ConflictError(
                "Category has items; deactivate it or move/delete its items first"
            )
        await self.db.delete(cat)
        await self.db.commit()


# ── Items ─────────────────────────────────────────────────────────────────────


class ItemUseCases:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list(
        self, tenant_id: str | None, category_id: str | None = None
    ) -> list[ItemResponseDTO]:
        field_count_subq = (
            select(
                ServiceCatalogFieldModel.item_id,
                func.count(ServiceCatalogFieldModel.id).label("cnt"),
            )
            .group_by(ServiceCatalogFieldModel.item_id)
            .subquery()
        )
        query = (
            select(
                ServiceCatalogItemModel,
                ServiceCatalogCategoryModel.name,
                field_count_subq.c.cnt,
            )
            .join(
                ServiceCatalogCategoryModel,
                ServiceCatalogCategoryModel.id == ServiceCatalogItemModel.category_id,
            )
            .outerjoin(
                field_count_subq,
                field_count_subq.c.item_id == ServiceCatalogItemModel.id,
            )
            .where(catalog_filter(ServiceCatalogItemModel, tenant_id))
        )
        if category_id:
            query = query.where(ServiceCatalogItemModel.category_id == category_id)
        query = query.order_by(
            ServiceCatalogItemModel.sort_order.asc(), ServiceCatalogItemModel.name.asc()
        )
        result = await self.db.execute(query)
        out: list[ItemResponseDTO] = []
        for item, cat_name, cnt in result.all():
            out.append(_item_to_dto(item, category_name=cat_name, field_count=cnt or 0))
        return out

    async def get(self, item_id: str) -> ItemResponseDTO:
        item = await self.db.get(ServiceCatalogItemModel, item_id)
        if not item:
            raise NotFoundError(f"Service item {item_id} not found")
        category = await self.db.get(ServiceCatalogCategoryModel, item.category_id)
        return _item_to_dto(
            item, category_name=category.name if category else None, field_count=0
        )

    async def create(
        self, dto: CreateItemDTO, tenant_id: str | None
    ) -> ItemResponseDTO:
        existing = await self.db.execute(
            select(ServiceCatalogItemModel).where(
                ServiceCatalogItemModel.tenant_id == tenant_id,
                ServiceCatalogItemModel.slug == dto.slug,
            )
        )
        if existing.scalar_one_or_none():
            raise ConflictError(f"Item slug '{dto.slug}' already exists")
        category = await self.db.get(ServiceCatalogCategoryModel, dto.category_id)
        if not category:
            raise NotFoundError(f"Category {dto.category_id} not found")
        item = ServiceCatalogItemModel(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            category_id=dto.category_id,
            name=dto.name,
            slug=dto.slug,
            description=dto.description,
            default_priority_id=dto.default_priority_id,
            default_team_id=dto.default_team_id,
            default_level=dto.default_level,
            sla_policy_id=dto.sla_policy_id,
            sort_order=dto.sort_order,
        )
        self.db.add(item)
        await self.db.commit()
        await self.db.refresh(item)
        return _item_to_dto(item, category_name=category.name, field_count=0)

    async def update(self, item_id: str, dto: UpdateItemDTO) -> ItemResponseDTO:
        item = await self.db.get(ServiceCatalogItemModel, item_id)
        if not item:
            raise NotFoundError(f"Service item {item_id} not found")
        for field, value in dto.model_dump(exclude_none=True).items():
            setattr(item, field, value)
        await self.db.commit()
        await self.db.refresh(item)
        category = await self.db.get(ServiceCatalogCategoryModel, item.category_id)
        return _item_to_dto(
            item, category_name=category.name if category else None, field_count=0
        )

    async def delete(self, item_id: str) -> None:
        item = await self.db.get(ServiceCatalogItemModel, item_id)
        if not item:
            raise NotFoundError(f"Service item {item_id} not found")
        from backend.src.modules.cases.infrastructure.models import CaseModel

        refs = await self.db.execute(
            select(CaseModel.id).where(CaseModel.service_item_id == item_id).limit(1)
        )
        if refs.scalar_one_or_none():
            raise ConflictError(
                "Item is referenced by existing cases; deactivate it instead"
            )
        await self.db.delete(item)
        await self.db.commit()


# ── Fields ────────────────────────────────────────────────────────────────────


class FieldUseCases:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_for_item(self, item_id: str) -> list[FieldResponseDTO]:
        result = await self.db.execute(
            select(ServiceCatalogFieldModel)
            .where(ServiceCatalogFieldModel.item_id == item_id)
            .order_by(ServiceCatalogFieldModel.sort_order.asc())
        )
        return [_field_to_dto(f) for f in result.scalars().all()]

    async def create(
        self, dto: CreateFieldDTO, tenant_id: str | None
    ) -> FieldResponseDTO:
        item = await self.db.get(ServiceCatalogItemModel, dto.item_id)
        if not item:
            raise NotFoundError(f"Service item {dto.item_id} not found")
        _validate_field_options(dto.field_type, dto.options)
        existing = await self.db.execute(
            select(ServiceCatalogFieldModel).where(
                ServiceCatalogFieldModel.item_id == dto.item_id,
                ServiceCatalogFieldModel.field_key == dto.field_key,
            )
        )
        if existing.scalar_one_or_none():
            raise ConflictError(
                f"Field key '{dto.field_key}' already exists for this item"
            )
        field_model = ServiceCatalogFieldModel(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            item_id=dto.item_id,
            field_key=dto.field_key,
            label=dto.label,
            field_type=dto.field_type,
            is_required=dto.is_required,
            placeholder=dto.placeholder,
            help_text=dto.help_text,
            options=[o.model_dump() for o in dto.options] if dto.options else None,
            validation=dto.validation,
            sort_order=dto.sort_order,
        )
        self.db.add(field_model)
        await self.db.commit()
        await self.db.refresh(field_model)
        return _field_to_dto(field_model)

    async def update(self, field_id: str, dto: UpdateFieldDTO) -> FieldResponseDTO:
        field_model = await self.db.get(ServiceCatalogFieldModel, field_id)
        if not field_model:
            raise NotFoundError(f"Field {field_id} not found")
        updated = dto.model_dump(exclude_none=True)
        # normalize options
        if "options" in updated and dto.options is not None:
            updated["options"] = [o.model_dump() for o in dto.options]
        new_type = updated.get("field_type", field_model.field_type)
        new_options = updated.get(
            "options",
            [FieldOption(**o) for o in field_model.options] if field_model.options else None,
        )
        if "options" in updated or "field_type" in updated:
            _validate_field_options(
                new_type,
                dto.options if dto.options is not None else
                ([FieldOption(**o) for o in field_model.options] if field_model.options else None),
            )
        for field, value in updated.items():
            setattr(field_model, field, value)
        await self.db.commit()
        await self.db.refresh(field_model)
        return _field_to_dto(field_model)

    async def delete(self, field_id: str) -> None:
        field_model = await self.db.get(ServiceCatalogFieldModel, field_id)
        if not field_model:
            raise NotFoundError(f"Field {field_id} not found")
        await self.db.delete(field_model)
        await self.db.commit()

    async def reorder(self, item_id: str, dto: ReorderFieldsDTO) -> list[FieldResponseDTO]:
        result = await self.db.execute(
            select(ServiceCatalogFieldModel).where(
                ServiceCatalogFieldModel.item_id == item_id
            )
        )
        current_fields = {f.id: f for f in result.scalars().all()}
        if set(dto.ordered_ids) != set(current_fields.keys()):
            raise ValidationError("ordered_ids must contain exactly the fields of the item")
        for idx, fid in enumerate(dto.ordered_ids):
            current_fields[fid].sort_order = idx
        await self.db.commit()
        return await self.list_for_item(item_id)


# ── Case custom values ────────────────────────────────────────────────────────


class CaseCustomValueUseCases:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_for_case(self, case_id: str) -> list[CaseCustomValueResponseDTO]:
        result = await self.db.execute(
            select(CaseCustomValueModel, ServiceCatalogFieldModel)
            .join(
                ServiceCatalogFieldModel,
                ServiceCatalogFieldModel.id == CaseCustomValueModel.field_id,
            )
            .where(CaseCustomValueModel.case_id == case_id)
            .order_by(ServiceCatalogFieldModel.sort_order.asc())
        )
        out: list[CaseCustomValueResponseDTO] = []
        for val, field_model in result.all():
            opts = (
                [FieldOption(**o) for o in field_model.options]
                if field_model.options
                else None
            )
            out.append(
                CaseCustomValueResponseDTO(
                    field_id=field_model.id,
                    field_key=field_model.field_key,
                    label=field_model.label,
                    field_type=field_model.field_type,
                    value=val.value,
                    options=opts,
                )
            )
        return out

    async def upsert_values(
        self,
        case_id: str,
        values: list[CaseCustomValueDTO],
        tenant_id: str | None,
    ) -> None:
        """Upsert a list of custom values for a case. Validates each value against its field."""
        field_ids = [v.field_id for v in values]
        if not field_ids:
            return
        result = await self.db.execute(
            select(ServiceCatalogFieldModel).where(
                ServiceCatalogFieldModel.id.in_(field_ids)
            )
        )
        fields = {f.id: f for f in result.scalars().all()}

        for v in values:
            field_model = fields.get(v.field_id)
            if not field_model:
                raise NotFoundError(f"Field {v.field_id} not found")
            _validate_field_value(field_model, v.value)

        # Load existing values and upsert
        result = await self.db.execute(
            select(CaseCustomValueModel).where(
                CaseCustomValueModel.case_id == case_id,
                CaseCustomValueModel.field_id.in_(field_ids),
            )
        )
        existing = {ex.field_id: ex for ex in result.scalars().all()}

        for v in values:
            if v.field_id in existing:
                existing[v.field_id].value = v.value
            else:
                self.db.add(
                    CaseCustomValueModel(
                        id=str(uuid.uuid4()),
                        tenant_id=tenant_id,
                        case_id=case_id,
                        field_id=v.field_id,
                        value=v.value,
                    )
                )
        await self.db.commit()


# ── Helpers ───────────────────────────────────────────────────────────────────


_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_PHONE_RE = re.compile(r"^\+?[\d\s\-()]{7,20}$")


def _validate_field_options(field_type: str, options: list[FieldOption] | None) -> None:
    requires_options = field_type in ("select", "radio", "multiselect")
    if requires_options and (not options or len(options) == 0):
        raise ValidationError(
            f"Field type '{field_type}' requires at least one option"
        )


def _validate_field_value(field_model: ServiceCatalogFieldModel, value: str | None) -> None:
    # Required
    if field_model.is_required and (value is None or value.strip() == ""):
        raise ValidationError(f"Field '{field_model.label}' is required")
    if value is None or value == "":
        return

    ftype = field_model.field_type
    val = value.strip()

    if ftype == "number":
        try:
            float(val)
        except ValueError:
            raise ValidationError(f"Field '{field_model.label}' must be a number")
    elif ftype == "email":
        if not _EMAIL_RE.match(val):
            raise ValidationError(f"Field '{field_model.label}' must be a valid email")
    elif ftype == "phone":
        if not _PHONE_RE.match(val):
            raise ValidationError(f"Field '{field_model.label}' must be a valid phone")
    elif ftype in ("select", "radio"):
        allowed = {o["value"] for o in (field_model.options or [])}
        if val not in allowed:
            raise ValidationError(
                f"Field '{field_model.label}' value '{val}' is not in allowed options"
            )
    elif ftype == "multiselect":
        try:
            picked = json.loads(val) if val.startswith("[") else val.split(",")
        except Exception:
            raise ValidationError(f"Field '{field_model.label}' must be JSON array or comma list")
        allowed = {o["value"] for o in (field_model.options or [])}
        if not all(p in allowed for p in picked):
            raise ValidationError(
                f"Field '{field_model.label}' contains values not in allowed options"
            )
    elif ftype == "checkbox":
        if val.lower() not in ("true", "false", "1", "0"):
            raise ValidationError(f"Field '{field_model.label}' must be boolean")

    # Optional validation metadata
    rules = field_model.validation or {}
    if rules:
        if "min_length" in rules and len(val) < int(rules["min_length"]):
            raise ValidationError(f"Field '{field_model.label}' is too short")
        if "max_length" in rules and len(val) > int(rules["max_length"]):
            raise ValidationError(f"Field '{field_model.label}' is too long")
        if "regex" in rules:
            pattern = rules["regex"]
            try:
                if not re.match(pattern, val):
                    raise ValidationError(f"Field '{field_model.label}' does not match pattern")
            except re.error:
                pass
        if ftype == "number":
            num = float(val)
            if "min" in rules and num < float(rules["min"]):
                raise ValidationError(f"Field '{field_model.label}' is below minimum")
            if "max" in rules and num > float(rules["max"]):
                raise ValidationError(f"Field '{field_model.label}' is above maximum")


def _category_to_dto(
    cat: ServiceCatalogCategoryModel, item_count: int
) -> CategoryResponseDTO:
    return CategoryResponseDTO(
        id=cat.id,
        name=cat.name,
        slug=cat.slug,
        description=cat.description,
        icon=cat.icon,
        color=cat.color,
        is_active=cat.is_active,
        sort_order=cat.sort_order,
        item_count=item_count,
    )


def _item_to_dto(
    item: ServiceCatalogItemModel,
    category_name: str | None,
    field_count: int,
) -> ItemResponseDTO:
    return ItemResponseDTO(
        id=item.id,
        category_id=item.category_id,
        category_name=category_name,
        name=item.name,
        slug=item.slug,
        description=item.description,
        default_priority_id=item.default_priority_id,
        default_team_id=item.default_team_id,
        default_level=item.default_level,
        sla_policy_id=item.sla_policy_id,
        is_active=item.is_active,
        sort_order=item.sort_order,
        field_count=field_count,
    )


def _field_to_dto(field_model: ServiceCatalogFieldModel) -> FieldResponseDTO:
    return FieldResponseDTO(
        id=field_model.id,
        item_id=field_model.item_id,
        field_key=field_model.field_key,
        label=field_model.label,
        field_type=field_model.field_type,  # type: ignore[arg-type]
        is_required=field_model.is_required,
        placeholder=field_model.placeholder,
        help_text=field_model.help_text,
        options=[FieldOption(**o) for o in field_model.options] if field_model.options else None,
        validation=field_model.validation,
        sort_order=field_model.sort_order,
    )
