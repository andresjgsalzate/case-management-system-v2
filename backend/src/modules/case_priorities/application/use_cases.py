import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.src.modules.case_priorities.infrastructure.models import CasePriorityModel
from backend.src.modules.case_priorities.application.dtos import (
    CreateCasePriorityDTO,
    CasePriorityResponseDTO,
)
from backend.src.core.exceptions import NotFoundError, ConflictError
from backend.src.core.tenant import catalog_filter


class CasePriorityUseCases:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_priority(
        self, dto: CreateCasePriorityDTO, tenant_id: str | None
    ) -> CasePriorityResponseDTO:
        priority = CasePriorityModel(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            name=dto.name,
            level=dto.level,
            color=dto.color,
            is_default=dto.is_default,
        )
        self.db.add(priority)
        await self.db.commit()
        await self.db.refresh(priority)
        return self._to_dto(priority)

    async def list_priorities(self, tenant_id: str | None) -> list[CasePriorityResponseDTO]:
        result = await self.db.execute(
            select(CasePriorityModel)
            .where(
                catalog_filter(CasePriorityModel, tenant_id),
                CasePriorityModel.is_active == True,
            )
            .order_by(CasePriorityModel.level)
        )
        return [self._to_dto(p) for p in result.scalars().all()]

    async def deactivate_priority(self, priority_id: str) -> None:
        from backend.src.modules.cases.infrastructure.models import CaseModel

        cases_using = await self.db.execute(
            select(CaseModel).where(CaseModel.priority_id == priority_id).limit(1)
        )
        if cases_using.scalar_one_or_none():
            raise ConflictError("Cannot delete priority: there are active cases using it")
        priority = await self.db.get(CasePriorityModel, priority_id)
        if not priority:
            raise NotFoundError(f"Priority {priority_id} not found")
        priority.is_active = False
        await self.db.commit()

    def _to_dto(self, model: CasePriorityModel) -> CasePriorityResponseDTO:
        return CasePriorityResponseDTO(
            id=model.id,
            name=model.name,
            level=model.level,
            color=model.color,
            is_default=model.is_default,
            is_active=model.is_active,
        )
