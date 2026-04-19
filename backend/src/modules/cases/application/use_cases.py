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
from backend.src.core.exceptions import NotFoundError, ValidationError, ForbiddenError
from backend.src.core.events.bus import event_bus
from backend.src.core.events.base import BaseEvent
from backend.src.core.permissions.case_queries import filter_cases_by_permission


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
                selectinload(CaseModel.assigned_user),
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
        user=None,
        queue: str = "all",
    ) -> tuple[list[CaseResponseDTO], int]:
        query = (
            select(CaseModel)
            .options(
                selectinload(CaseModel.status),
                selectinload(CaseModel.priority),
                selectinload(CaseModel.application),
                selectinload(CaseModel.origin),
                selectinload(CaseModel.assigned_user),
            )
            .where(CaseModel.tenant_id == tenant_id, CaseModel.is_archived == False)
        )

        if user is not None:
            query = filter_cases_by_permission(query, user, queue=queue)  # type: ignore[arg-type]
        elif scope == "own":
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
        old_priority_id = case.priority_id
        updated_fields = dto.model_dump(exclude_none=True)
        new_priority_id = updated_fields.get("priority_id")
        for field, value in updated_fields.items():
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
        if new_priority_id is not None and new_priority_id != old_priority_id:
            await event_bus.publish(
                BaseEvent(
                    event_name="case.priority_changed",
                    tenant_id=tenant_id,
                    actor_id=actor_id,
                    payload={
                        "case_id": case_id,
                        "from_priority_id": old_priority_id,
                        "to_priority_id": new_priority_id,
                    },
                )
            )
        return await self.get_case(case_id)

    async def transition_case(
        self, case_id: str, dto: TransitionCaseDTO, actor_id: str, tenant_id: str
    ) -> CaseResponseDTO:
        from backend.src.modules.users.infrastructure.models import UserModel
        from backend.src.modules.assignment.infrastructure.models import CaseAssignmentModel
        from backend.src.modules.notes.infrastructure.models import CaseNoteModel
        from backend.src.modules.chat.infrastructure.models import ChatMessageModel

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
        old_status_id = case.status_id  # guardar antes de sobrescribir
        case.status_id = dto.target_status_id
        if target_status.is_final:
            case.closed_at = datetime.now(timezone.utc)

        await self.db.commit()

        # Al marcar como resuelto: auto-crear solicitud de confirmación al reportador
        if target_status.slug == "resolved":
            import json as _json
            from backend.src.modules.resolution.infrastructure.models import CaseResolutionRequestModel

            actor_user = await self.db.get(UserModel, actor_id)
            actor_name = actor_user.full_name if actor_user else "Agente"

            reporter_user = await self.db.get(UserModel, case.created_by)
            reporter_name = reporter_user.full_name if reporter_user else "Solicitante"

            request_id = str(uuid.uuid4())
            chat_msg_id = str(uuid.uuid4())

            # Nota de auditoría
            self.db.add(CaseNoteModel(
                id=str(uuid.uuid4()),
                case_id=case_id,
                user_id=actor_id,
                tenant_id=tenant_id,
                content=f"Caso marcado como Resuelto por {actor_name}. Se envió solicitud de confirmación a {reporter_name}.",
            ))

            # Mensaje de chat tipo resolution_request
            self.db.add(ChatMessageModel(
                id=chat_msg_id,
                case_id=case_id,
                user_id=actor_id,
                tenant_id=tenant_id,
                content_type="resolution_request",
                content=_json.dumps({
                    "request_id": request_id,
                    "requested_by_name": actor_name,
                    "status": "pending",
                    "rating": None,
                    "observation": None,
                    "responded_by_name": None,
                    "responded_at": None,
                }, ensure_ascii=False),
            ))

            # Registro en la tabla de resoluciones
            self.db.add(CaseResolutionRequestModel(
                id=request_id,
                case_id=case_id,
                tenant_id=tenant_id,
                chat_message_id=chat_msg_id,
                requested_by=actor_id,
                requested_at=datetime.now(timezone.utc),
                status="pending",
                previous_status_id=old_status_id,
            ))

            await self.db.commit()

            from backend.src.core.websocket_manager import manager as _ws_manager
            await _ws_manager.broadcast(
                case_id=case_id,
                message={"type": "new_message", "data": {"id": chat_msg_id}},
            )

            await event_bus.publish(
                BaseEvent(
                    event_name="resolution.requested",
                    tenant_id=tenant_id,
                    actor_id=actor_id,
                    payload={
                        "case_id": case_id,
                        "request_id": request_id,
                        "requested_by_name": actor_name,
                        "reporter_name": reporter_name,
                    },
                )
            )

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

    async def list_archived(
        self,
        tenant_id: str | None,
        actor_id: str,
        scope: str,
        search: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[CaseResponseDTO], int]:
        query = (
            select(CaseModel)
            .options(
                selectinload(CaseModel.status),
                selectinload(CaseModel.priority),
                selectinload(CaseModel.application),
                selectinload(CaseModel.origin),
                selectinload(CaseModel.assigned_user),
            )
            .where(CaseModel.tenant_id == tenant_id, CaseModel.is_archived == True)
        )

        if scope == "own":
            query = query.where(CaseModel.created_by == actor_id)
        if search:
            like = f"%{search}%"
            from sqlalchemy import or_
            query = query.where(
                or_(
                    CaseModel.title.ilike(like),
                    CaseModel.case_number.ilike(like),
                )
            )
        count_result = await self.db.execute(
            select(func.count()).select_from(query.subquery())
        )
        total = count_result.scalar()
        result = await self.db.execute(
            query.offset((page - 1) * page_size)
            .limit(page_size)
            .order_by(CaseModel.archived_at.desc())
        )
        return [self._to_dto(c) for c in result.scalars().all()], total

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
            assigned_user_name=model.assigned_user.full_name if model.assigned_user else None,
            team_id=model.team_id,
            solution_description=model.solution_description,
            is_archived=model.is_archived,
            archived_at=model.archived_at.isoformat() if model.archived_at else None,
            archived_by=model.archived_by,
            closed_at=model.closed_at.isoformat() if model.closed_at else None,
            created_at=model.created_at.isoformat(),
            updated_at=model.updated_at.isoformat(),
        )
