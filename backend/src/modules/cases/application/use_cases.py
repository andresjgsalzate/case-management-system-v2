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
from backend.src.core.permissions.case_permissions import check_case_action
from backend.src.modules.service_catalog.infrastructure.models import (
    ServiceCatalogItemModel,
)


class CaseUseCases:
    def __init__(self, db: AsyncSession):
        self.db = db

    # Mapping from case_type → case number prefix
    _PREFIX_BY_TYPE: dict[str, str] = {
        "request": "REQ",
        "incident": "INC",
        "event": "EVT",
    }

    # Default initial status slug per case_type
    _DEFAULT_STATUS_SLUG: dict[str, str] = {
        "request": "new",
        "incident": "new",
        "event": "logged",
    }

    async def create_case(
        self, dto: CreateCaseDTO, actor_id: str, tenant_id: str | None
    ) -> CaseResponseDTO:
        from backend.src.modules.service_catalog.infrastructure.models import (
            ServiceCatalogItemModel,
        )
        from backend.src.modules.service_catalog.application.use_cases import (
            CaseCustomValueUseCases,
        )
        from backend.src.modules.service_catalog.application.dtos import (
            CaseCustomValueDTO,
        )

        # Validate case_type (Pydantic Literal already does this, but guard for
        # callers that bypass the DTO, e.g. direct use_case calls in tests)
        case_type = dto.case_type
        if case_type not in self._PREFIX_BY_TYPE:
            raise ValidationError(
                f"Invalid case_type '{case_type}'. Must be one of: {list(self._PREFIX_BY_TYPE)}"
            )

        # Generate case number using the per-type prefix
        prefix = self._PREFIX_BY_TYPE[case_type]
        case_number = await self._next_case_number(tenant_id, prefix)

        # Resolve initial status: explicit slug overrides default per type
        status_slug = dto.initial_status_slug or self._DEFAULT_STATUS_SLUG[case_type]
        initial_status = await self._get_status_by_slug(tenant_id, status_slug)
        if initial_status is None:
            raise ValidationError(
                f"Status with slug '{status_slug}' not found for tenant {tenant_id}"
            )

        # Validate status applies to this case_type
        applies = initial_status.applies_to_case_types or []
        if case_type not in applies:
            raise ValidationError(
                f"Status '{status_slug}' does not apply to case_type '{case_type}'. "
                f"applies_to_case_types={applies}"
            )

        # Resolver service item y aplicar defaults si vienen vacíos
        priority_id = dto.priority_id
        team_id: str | None = None
        current_level = 1
        service_item: ServiceCatalogItemModel | None = None
        if dto.service_item_id:
            service_item = await self.db.get(
                ServiceCatalogItemModel, dto.service_item_id
            )
            if not service_item:
                raise NotFoundError(f"Service item {dto.service_item_id} not found")
            if not priority_id and service_item.default_priority_id:
                priority_id = service_item.default_priority_id
            team_id = service_item.default_team_id
            current_level = service_item.default_level

        if not priority_id:
            raise ValidationError("priority_id is required (or use a service_item with default)")

        case = CaseModel(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            case_number=case_number,
            case_type=case_type,
            title=dto.title,
            description=dto.description,
            status_id=initial_status.id,
            priority_id=priority_id,
            complexity=dto.complexity,
            application_id=dto.application_id,
            origin_id=dto.origin_id,
            service_item_id=dto.service_item_id,
            team_id=team_id,
            current_level=current_level,
            created_by=actor_id,
        )
        self.db.add(case)
        await self.db.commit()
        await self.db.refresh(case)

        # Persistir custom values (validados contra los fields del item)
        if dto.custom_values:
            cv_uc = CaseCustomValueUseCases(self.db)
            await cv_uc.upsert_values(
                case_id=case.id,
                values=[CaseCustomValueDTO(field_id=v.field_id, value=v.value) for v in dto.custom_values],
                tenant_id=tenant_id,
            )

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
                selectinload(CaseModel.service_item).selectinload(
                    ServiceCatalogItemModel.category
                ),
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
                selectinload(CaseModel.service_item).selectinload(
                    ServiceCatalogItemModel.category
                ),
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
        self, case_id: str, dto: UpdateCaseDTO, actor_id: str, tenant_id: str, user=None
    ) -> CaseResponseDTO:
        from backend.src.modules.users.infrastructure.models import UserModel
        case = await self.db.get(CaseModel, case_id)
        if not case:
            raise NotFoundError(f"Case {case_id} not found")
        if user is not None and not check_case_action(user, case, "update"):
            raise ForbiddenError("Cannot update this case")
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
        self, case_id: str, dto: TransitionCaseDTO, actor_id: str, tenant_id: str, user=None
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
        if user is not None and not check_case_action(user, case, "transition"):
            raise ForbiddenError("Cannot transition this case")

        target_status = await self.db.get(CaseStatusModel, dto.target_status_id)
        if not target_status:
            raise NotFoundError(f"Status {dto.target_status_id} not found")

        # Validate the status applies to the case's case_type (sub-spec 01 § 4.4)
        if case.case_type not in (target_status.applies_to_case_types or []):
            raise ValidationError(
                f"Status '{target_status.slug}' does not apply to cases of type "
                f"'{case.case_type}'. applies_to_case_types={target_status.applies_to_case_types}"
            )

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

    async def search_cases(
        self,
        tenant_id: str | None,
        q: str,
        user,
        limit: int = 10,
    ) -> list[CaseResponseDTO]:
        """Search cases by case_number or title across active AND archived,
        respecting RBAC scope/level via filter_cases_by_permission."""
        from sqlalchemy import or_
        like = f"%{q.strip()}%"
        query = (
            select(CaseModel)
            .options(
                selectinload(CaseModel.status),
                selectinload(CaseModel.priority),
                selectinload(CaseModel.application),
                selectinload(CaseModel.origin),
                selectinload(CaseModel.assigned_user),
                selectinload(CaseModel.service_item).selectinload(
                    ServiceCatalogItemModel.category
                ),
            )
            .where(CaseModel.tenant_id == tenant_id)
            .where(
                or_(
                    CaseModel.case_number.ilike(like),
                    CaseModel.title.ilike(like),
                )
            )
        )
        query = filter_cases_by_permission(query, user, queue="all")
        result = await self.db.execute(
            query.order_by(CaseModel.created_at.desc()).limit(limit)
        )
        return [self._to_dto(c) for c in result.scalars().all()]

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
                selectinload(CaseModel.service_item).selectinload(
                    ServiceCatalogItemModel.category
                ),
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

    async def _get_status_by_slug(
        self, tenant_id: str | None, slug: str
    ) -> "CaseStatusModel | None":
        """Return the CaseStatusModel matching slug for the given tenant (or global)."""
        from backend.src.core.tenant import catalog_filter

        result = await self.db.execute(
            select(CaseStatusModel).where(
                catalog_filter(CaseStatusModel, tenant_id),
                CaseStatusModel.slug == slug,
            )
        )
        return result.scalar_one_or_none()

    async def _next_case_number(self, tenant_id, prefix: str) -> str:
        """Atomically increment the active range for (tenant_id, prefix) and return
        a formatted case number like 'INC-2026-000047'.

        Uses SELECT FOR UPDATE to serialize concurrent calls at the DB row level.
        The first transaction that acquires the lock reads the latest current_number,
        increments it, and flushes — subsequent concurrent transactions wait and then
        see the already-incremented value, guaranteeing uniqueness.
        """
        from backend.src.modules.cases.infrastructure.models import CaseNumberRangeModel

        tenant_clause = (
            CaseNumberRangeModel.tenant_id.is_(None)
            if tenant_id is None
            else CaseNumberRangeModel.tenant_id == tenant_id
        )

        result = await self.db.execute(
            select(CaseNumberRangeModel)
            .where(
                tenant_clause,
                CaseNumberRangeModel.prefix == prefix,
                CaseNumberRangeModel.current_number < CaseNumberRangeModel.range_end,
            )
            .order_by(CaseNumberRangeModel.range_start)
            .with_for_update()
            .limit(1)
        )
        range_row = result.scalar_one_or_none()
        if range_row is None:
            raise ValueError(
                f"No active number range for {prefix} in tenant {tenant_id}. "
                "Create a new range or extend the existing one."
            )

        range_row.current_number += 1
        await self.db.flush()
        year = datetime.now(timezone.utc).year
        return f"{prefix}-{year}-{range_row.current_number:06d}"

    def _to_dto(self, model: CaseModel) -> CaseResponseDTO:
        # service_item y su category vienen via selectinload — accedemos sin lazy
        svc_item = getattr(model, "service_item", None)
        svc_category = svc_item.category if svc_item is not None else None
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
            service_item_id=model.service_item_id,
            service_item_name=svc_item.name if svc_item else None,
            service_category_id=svc_category.id if svc_category else None,
            service_category_name=svc_category.name if svc_category else None,
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
