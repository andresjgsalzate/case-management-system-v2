import re
import uuid
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.src.modules.tenants.infrastructure.models import TenantModel
from backend.src.core.exceptions import NotFoundError, ConflictError


class CreateTenantDTO(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    slug: str = Field(min_length=2, max_length=100)
    description: str | None = None


class UpdateTenantDTO(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=200)
    description: str | None = None
    is_active: bool | None = None


class TenantResponseDTO(BaseModel):
    id: str
    name: str
    slug: str
    description: str | None
    is_active: bool
    created_at: str


def _normalize_slug(slug: str) -> str:
    return re.sub(r"[^a-z0-9-]", "-", slug.lower().strip())


class TenantUseCases:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list(self) -> list[TenantResponseDTO]:
        result = await self.db.execute(select(TenantModel).order_by(TenantModel.name))
        return [self._to_dto(t) for t in result.scalars().all()]

    async def get(self, tenant_id: str) -> TenantResponseDTO:
        tenant = await self.db.get(TenantModel, tenant_id)
        if not tenant:
            raise NotFoundError("Tenant", tenant_id)
        return self._to_dto(tenant)

    async def create(self, dto: CreateTenantDTO) -> TenantResponseDTO:
        slug = _normalize_slug(dto.slug)

        existing = await self.db.execute(
            select(TenantModel).where(
                (TenantModel.slug == slug) | (TenantModel.name == dto.name)
            )
        )
        if existing.scalar_one_or_none():
            raise ConflictError(f"Tenant con nombre '{dto.name}' o slug '{slug}' ya existe")

        tenant = TenantModel(
            id=str(uuid.uuid4()),
            name=dto.name,
            slug=slug,
            description=dto.description,
        )
        self.db.add(tenant)
        await self.db.commit()
        await self.db.refresh(tenant)
        return self._to_dto(tenant)

    async def update(self, tenant_id: str, dto: UpdateTenantDTO) -> TenantResponseDTO:
        tenant = await self.db.get(TenantModel, tenant_id)
        if not tenant:
            raise NotFoundError("Tenant", tenant_id)

        if dto.name is not None:
            conflict = await self.db.execute(
                select(TenantModel).where(
                    TenantModel.name == dto.name,
                    TenantModel.id != tenant_id,
                )
            )
            if conflict.scalar_one_or_none():
                raise ConflictError(f"Ya existe un tenant con el nombre '{dto.name}'")
            tenant.name = dto.name

        if dto.description is not None:
            tenant.description = dto.description
        if dto.is_active is not None:
            tenant.is_active = dto.is_active

        await self.db.commit()
        await self.db.refresh(tenant)
        return self._to_dto(tenant)

    async def delete(self, tenant_id: str) -> None:
        tenant = await self.db.get(TenantModel, tenant_id)
        if not tenant:
            raise NotFoundError("Tenant", tenant_id)
        await self.db.delete(tenant)
        await self.db.commit()

    def _to_dto(self, model: TenantModel) -> TenantResponseDTO:
        return TenantResponseDTO(
            id=model.id,
            name=model.name,
            slug=model.slug,
            description=model.description,
            is_active=model.is_active,
            created_at=model.created_at.isoformat(),
        )
