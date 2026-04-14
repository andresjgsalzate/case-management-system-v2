import uuid
from sqlalchemy.ext.asyncio import AsyncSession

from backend.src.modules.cases.infrastructure.models import CaseModel
from backend.src.modules.assignment.infrastructure.models import CaseAssignmentModel
from backend.src.core.exceptions import NotFoundError, PermissionDeniedError
from backend.src.core.events.bus import event_bus
from backend.src.core.events.base import BaseEvent


class AssignmentUseCases:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def assign_case(
        self,
        case_id: str,
        assigned_to: str | None,
        team_id: str | None,
        actor_id: str,
        tenant_id: str,
    ) -> None:
        from backend.src.modules.users.infrastructure.models import UserModel

        case = await self.db.get(CaseModel, case_id)
        if not case:
            raise NotFoundError(f"Case {case_id} not found")
        if case.is_archived:
            raise PermissionDeniedError("Cannot assign an archived case")

        # Capturar asignado anterior antes de modificar
        old_assigned_to = case.assigned_to
        old_user = await self.db.get(UserModel, old_assigned_to) if old_assigned_to else None
        old_assigned_to_name = old_user.full_name if old_user else None

        # Obtener nombre del nuevo asignado
        assigned_to_name = None
        if assigned_to:
            new_user = await self.db.get(UserModel, assigned_to)
            if new_user:
                assigned_to_name = new_user.full_name

        # Obtener nombre del actor (quien asigna)
        actor = await self.db.get(UserModel, actor_id)
        assigned_by_name = actor.full_name if actor else None

        case.assigned_to = assigned_to
        case.team_id = team_id

        assignment = CaseAssignmentModel(
            id=str(uuid.uuid4()),
            case_id=case_id,
            assigned_to=assigned_to,
            assigned_by=actor_id,
            team_id=team_id,
        )
        self.db.add(assignment)
        await self.db.commit()

        await event_bus.publish(
            BaseEvent(
                event_name="case.assigned",
                tenant_id=tenant_id,
                actor_id=actor_id,
                payload={
                    "case_id": case_id,
                    "case_number": case.case_number,
                    "case_title": case.title,
                    "assigned_to": assigned_to,
                    "assigned_to_name": assigned_to_name,
                    "assigned_by_name": assigned_by_name,
                    "from_assigned_to": old_assigned_to,
                    "from_assigned_to_name": old_assigned_to_name,
                    "team_id": team_id,
                },
            )
        )
