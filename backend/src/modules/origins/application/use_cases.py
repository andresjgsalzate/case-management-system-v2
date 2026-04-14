import uuid
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.src.modules.origins.infrastructure.models import OriginModel
from backend.src.core.exceptions import NotFoundError, ConflictError
from backend.src.core.tenant import catalog_filter


class CreateOriginDTO(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    code: str = Field(min_length=2, max_length=50)
    description: str | None = None


class OriginResponseDTO(BaseModel):
    id: str
    name: str
    code: str
    description: str | None
    is_active: bool


class OriginUseCases:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, dto: CreateOriginDTO, tenant_id: str | None) -> OriginResponseDTO:
        existing = await self.db.execute(
            select(OriginModel).where(
                OriginModel.code == dto.code.upper(),
                OriginModel.tenant_id == tenant_id,
            )
        )
        if existing.scalar_one_or_none():
            raise ConflictError(f"Origin code '{dto.code}' already exists")
        origin = OriginModel(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            name=dto.name,
            code=dto.code.upper(),
            description=dto.description,
        )
        self.db.add(origin)
        await self.db.commit()
        await self.db.refresh(origin)
        return OriginResponseDTO(
            id=origin.id,
            name=origin.name,
            code=origin.code,
            description=origin.description,
            is_active=origin.is_active,
        )

    async def list(self, tenant_id: str | None) -> list[OriginResponseDTO]:
        result = await self.db.execute(
            select(OriginModel).where(
                catalog_filter(OriginModel, tenant_id),
                OriginModel.is_active == True,
            )
        )
        return [
            OriginResponseDTO(
                id=o.id,
                name=o.name,
                code=o.code,
                description=o.description,
                is_active=o.is_active,
            )
            for o in result.scalars().all()
        ]

    async def deactivate(self, origin_id: str) -> None:
        from backend.src.modules.cases.infrastructure.models import CaseModel

        cases = await self.db.execute(
            select(CaseModel).where(CaseModel.origin_id == origin_id).limit(1)
        )
        if cases.scalar_one_or_none():
            raise ConflictError("Cannot delete: origin has associated cases.")
        origin = await self.db.get(OriginModel, origin_id)
        if not origin:
            raise NotFoundError(f"Origin {origin_id} not found")
        origin.is_active = False
        await self.db.commit()
