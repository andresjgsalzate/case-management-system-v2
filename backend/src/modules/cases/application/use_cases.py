import csv
import io
import uuid
from datetime import datetime, timezone

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.src.modules.cases.infrastructure.models import CaseModel
from backend.src.modules.case_statuses.infrastructure.models import CaseStatusModel
from backend.src.modules.case_statuses.application.use_cases import (
    validate_transition,
    CaseStatusUseCases,
)
from backend.src.modules.cases.application.number_service import next_case_number
from backend.src.modules.cases.application.dtos import (
    CreateCaseDTO,
    UpdateCaseDTO,
    TransitionCaseDTO,
    CaseResponseDTO,
)
from backend.src.core.exceptions import NotFoundError, ValidationError
from backend.src.core.events.bus import event_bus
from backend.src.core.events.base import BaseEvent


class CaseUseCases:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_case(
        self, dto: CreateCaseDTO, actor_id: str, tenant_id: str | None
    ) -> CaseResponseDTO:
        status_uc = CaseStatusUseCases(self.db)
        initial_status = await status_uc.get_initial_status(tenant_id)
        case_number = await next_case_number(self.db, tenant_id)

        case = CaseModel(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            case_number=case_number,
            title=dto.title,
            description=dto.description,
            status_id=initial_status.id,
            priority_id=dto.priority_id,
            complexity=dto.complexity,
            application_id=dto.application_id,
            origin_id=dto.origin_id,
            created_by=actor_id,
        )
        self.db.add(case)
        await self.db.commit()
        await self.db.refresh(case)

        await event_bus.publish(
            BaseEvent(
                event_name="case.created",
                tenant_id=tenant_id or "default",
                actor_id=actor_id,
                payload={"case_id": case.id, "case_number": case_number, "title": dto.title},
            )
        )

        return await self.get_case(case.id)

    async def get_case(self, case_id: str) -> CaseResponseDTO:
        result = await self.db.execute(
            select(CaseModel)
            .options(
                selectinload(CaseModel.status),
                selectinload(CaseModel.priority),
                selectinload(CaseModel.application),
                selectinload(CaseModel.origin),
            )
            .where(CaseModel.id == case_id)
        )
        case = result.scalar_one_or_none()
        if not case:
            raise NotFoundError(f"Case {case_id} not found")
        return self._to_dto(case)

    async def list_cases(
        self,
        tenant_id: str | None,
        actor_id: str,
        scope: str,
        page: int,
        page_size: int,
        filters: dict | None = None,
    ) -> tuple[list[CaseResponseDTO], int]:
        query = (
            select(CaseModel)
            .options(
                selectinload(CaseModel.status),
                selectinload(CaseModel.priority),
                selectinload(CaseModel.application),
                selectinload(CaseModel.origin),
            )
            .where(CaseModel.tenant_id == tenant_id, CaseModel.is_archived == False)
        )

        if scope == "own":
            query = query.where(CaseModel.created_by == actor_id)

        if filters:
            if status_id := filters.get("status_id"):
                query = query.where(CaseModel.status_id == status_id)
            if priority_id := filters.get("priority_id"):
                query = query.where(CaseModel.priority_id == priority_id)
            if assigned_to := filters.get("assigned_to"):
                query = query.where(CaseModel.assigned_to == assigned_to)

        count_result = await self.db.execute(
            select(func.count()).select_from(query.subquery())
        )
        total = count_result.scalar()
        result = await self.db.execute(
            query.offset((page - 1) * page_size)
            .limit(page_size)
            .order_by(CaseModel.created_at.desc())
        )
        return [self._to_dto(c) for c in result.scalars().all()], total

    async def update_case(
        self, case_id: str, dto: UpdateCaseDTO, actor_id: str, tenant_id: str
    ) -> CaseResponseDTO:
        from backend.src.modules.users.infrastructure.models import UserModel
        case = await self.db.get(CaseModel, case_id)
        if not case:
            raise NotFoundError(f"Case {case_id} not found")
        assigned_to = case.assigned_to
        for field, value in dto.model_dump(exclude_none=True).items():
            setattr(case, field, value)
        await self.db.commit()
        actor = await self.db.get(UserModel, actor_id)
        await event_bus.publish(
            BaseEvent(
                event_name="case.updated",
                tenant_id=tenant_id,
                actor_id=actor_id,
                payload={
                    "case_id": case_id,
                    "case_number": case.case_number,
                    "case_title": case.title,
                    "assigned_to": assigned_to,
                    "updated_by": actor.full_name if actor else "Sistema",
                },
            )
        )
        return await self.get_case(case_id)

    async def transition_case(
        self, case_id: str, dto: TransitionCaseDTO, actor_id: str, tenant_id: str
    ) -> CaseResponseDTO:
        result = await self.db.execute(
            select(CaseModel)
            .options(selectinload(CaseModel.status))
            .where(CaseModel.id == case_id)
        )
        case = result.scalar_one_or_none()
        if not case:
            raise NotFoundError(f"Case {case_id} not found")

        target_status = await self.db.get(CaseStatusModel, dto.target_status_id)
        if not target_status:
            raise NotFoundError(f"Status {dto.target_status_id} not found")

        validate_transition(target_status.slug, case.status.allowed_transitions or [])

        if target_status.slug == "closed":
            if not dto.solution_description or not dto.solution_description.strip():
                raise ValidationError("Se requiere una descripción de la solución para cerrar el caso")
            case.solution_description = dto.solution_description.strip()

        old_status_name = case.status.name
        case.status_id = dto.target_status_id
        if target_status.is_final:
            case.closed_at = datetime.now(timezone.utc)

        await self.db.commit()

        await event_bus.publish(
            BaseEvent(
                event_name="case.status_changed",
                tenant_id=tenant_id,
                actor_id=actor_id,
                payload={
                    "case_id": case_id,
                    "case_number": case.case_number,
                    "case_title": case.title,
                    "created_by": case.created_by,
                    "from_status": old_status_name,
                    "to_status": target_status.name,
                    "to_status_id": target_status.id,
                },
            )
        )

        if target_status.is_final:
            await event_bus.publish(
                BaseEvent(
                    event_name="case.closed",
                    tenant_id=tenant_id,
                    actor_id=actor_id,
                    payload={"case_id": case_id},
                )
            )

        return await self.get_case(case_id)

    async def export_csv(self, tenant_id: str | None) -> str:
        result = await self.db.execute(
            select(CaseModel)
            .options(selectinload(CaseModel.status), selectinload(CaseModel.priority))
            .where(CaseModel.tenant_id == tenant_id, CaseModel.is_archived == False)
            .order_by(CaseModel.created_at.desc())
        )
        cases = result.scalars().all()

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(
            ["case_number", "title", "status", "priority", "complexity", "created_at", "assigned_to"]
        )
        for c in cases:
            writer.writerow(
                [
                    c.case_number,
                    c.title,
                    c.status.name if c.status else "",
                    c.priority.name if c.priority else "",
                    c.complexity,
                    c.created_at.isoformat(),
                    c.assigned_to or "",
                ]
            )
        return output.getvalue()

    def _to_dto(self, model: CaseModel) -> CaseResponseDTO:
        return CaseResponseDTO(
            id=model.id,
            case_number=model.case_number,
            title=model.title,
            description=model.description,
            status_id=model.status_id,
            status_name=model.status.name if model.status else "",
            status_slug=model.status.slug if model.status else "",
            status_color=model.status.color if model.status else "",
            priority_id=model.priority_id,
            priority_name=model.priority.name if model.priority else "",
            priority_color=model.priority.color if model.priority else "",
            complexity=model.complexity,
            application_id=model.application_id,
            application_name=model.application.name if model.application else None,
            origin_id=model.origin_id,
            origin_name=model.origin.name if model.origin else None,
            created_by=model.created_by,
            assigned_to=model.assigned_to,
            team_id=model.team_id,
            solution_description=model.solution_description,
            is_archived=model.is_archived,
            closed_at=model.closed_at.isoformat() if model.closed_at else None,
            created_at=model.created_at.isoformat(),
            updated_at=model.updated_at.isoformat(),
        )
