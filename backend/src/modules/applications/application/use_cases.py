import uuid
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.src.modules.applications.infrastructure.models import ApplicationModel
from backend.src.core.exceptions import NotFoundError, ConflictError


class CreateApplicationDTO(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    code: str = Field(min_length=2, max_length=50)
    description: str | None = None


class ApplicationResponseDTO(BaseModel):
    id: str
    name: str
    code: str
    description: str | None
    is_active: bool


class ApplicationUseCases:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(
        self, dto: CreateApplicationDTO, tenant_id: str | None
    ) -> ApplicationResponseDTO:
        existing = await self.db.execute(
            select(ApplicationModel).where(
                ApplicationModel.code == dto.code.upper(),
                ApplicationModel.tenant_id == tenant_id,
            )
        )
        if existing.scalar_one_or_none():
            raise ConflictError(f"Application code '{dto.code}' already exists")
        app = ApplicationModel(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            name=dto.name,
            code=dto.code.upper(),
            description=dto.description,
        )
        self.db.add(app)
        await self.db.commit()
        await self.db.refresh(app)
        return ApplicationResponseDTO(
            id=app.id,
            name=app.name,
            code=app.code,
            description=app.description,
            is_active=app.is_active,
        )

    async def list(self, tenant_id: str | None) -> list[ApplicationResponseDTO]:
        result = await self.db.execute(
            select(ApplicationModel).where(
                ApplicationModel.tenant_id == tenant_id,
                ApplicationModel.is_active == True,
            )
        )
        return [
            ApplicationResponseDTO(
                id=a.id,
                name=a.name,
                code=a.code,
                description=a.description,
                is_active=a.is_active,
            )
            for a in result.scalars().all()
        ]

    async def deactivate(self, app_id: str) -> None:
        from backend.src.modules.cases.infrastructure.models import CaseModel

        cases = await self.db.execute(
            select(CaseModel).where(CaseModel.application_id == app_id).limit(1)
        )
        if cases.scalar_one_or_none():
            raise ConflictError(
                "Cannot delete: application has associated cases. Deactivate instead."
            )
        app = await self.db.get(ApplicationModel, app_id)
        if not app:
            raise NotFoundError(f"Application {app_id} not found")
        app.is_active = False
        await self.db.commit()
