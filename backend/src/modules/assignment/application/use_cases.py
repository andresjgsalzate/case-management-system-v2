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
        case = await self.db.get(CaseModel, case_id)
        if not case:
            raise NotFoundError(f"Case {case_id} not found")
        if case.is_archived:
            raise PermissionDeniedError("Cannot assign an archived case")

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
                    "assigned_to": assigned_to,
                    "team_id": team_id,
                },
            )
        )
