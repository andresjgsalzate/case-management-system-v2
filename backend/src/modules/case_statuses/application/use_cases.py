import uuid
import re
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.src.modules.case_statuses.infrastructure.models import CaseStatusModel
from backend.src.modules.case_statuses.application.dtos import (
    CreateCaseStatusDTO,
    CaseStatusResponseDTO,
)
from backend.src.core.exceptions import NotFoundError, ConflictError, BusinessRuleError


def _slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


def validate_transition(target_slug: str, allowed_transitions: list[str]) -> bool:
    if target_slug not in allowed_transitions:
        raise BusinessRuleError(
            f"Transition to '{target_slug}' is not allowed. Allowed: {allowed_transitions}"
        )
    return True


class CaseStatusUseCases:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_status(
        self, dto: CreateCaseStatusDTO, tenant_id: str | None
    ) -> CaseStatusResponseDTO:
        slug = _slugify(dto.name)
        status = CaseStatusModel(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            name=dto.name,
            slug=slug,
            color=dto.color,
            order=dto.order,
            is_initial=dto.is_initial,
            is_final=dto.is_final,
            allowed_transitions=dto.allowed_transitions,
        )
        self.db.add(status)
        await self.db.commit()
        await self.db.refresh(status)
        return self._to_dto(status)

    async def list_statuses(self, tenant_id: str | None) -> list[CaseStatusResponseDTO]:
        result = await self.db.execute(
            select(CaseStatusModel)
            .where(CaseStatusModel.tenant_id == tenant_id)
            .order_by(CaseStatusModel.order)
        )
        return [self._to_dto(s) for s in result.scalars().all()]

    async def get_initial_status(self, tenant_id: str | None) -> CaseStatusModel:
        result = await self.db.execute(
            select(CaseStatusModel).where(
                CaseStatusModel.tenant_id == tenant_id,
                CaseStatusModel.is_initial == True,
            )
        )
        status = result.scalar_one_or_none()
        if not status:
            raise BusinessRuleError(
                "No initial status configured. Please set up case statuses first."
            )
        return status

    async def delete_status(self, status_id: str) -> None:
        from backend.src.modules.cases.infrastructure.models import CaseModel

        cases_using = await self.db.execute(
            select(CaseModel).where(CaseModel.status_id == status_id).limit(1)
        )
        if cases_using.scalar_one_or_none():
            raise ConflictError("Cannot delete status: there are active cases using it")
        status = await self.db.get(CaseStatusModel, status_id)
        if not status:
            raise NotFoundError(f"Status {status_id} not found")
        await self.db.delete(status)
        await self.db.commit()

    def _to_dto(self, model: CaseStatusModel) -> CaseStatusResponseDTO:
        return CaseStatusResponseDTO(
            id=model.id,
            name=model.name,
            slug=model.slug,
            color=model.color,
            order=model.order,
            is_initial=model.is_initial,
            is_final=model.is_final,
            allowed_transitions=model.allowed_transitions or [],
            created_at=model.created_at.isoformat(),
        )
