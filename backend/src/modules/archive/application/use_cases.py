from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from backend.src.modules.cases.infrastructure.models import CaseModel
from backend.src.core.exceptions import NotFoundError, ConflictError
from backend.src.core.events.bus import event_bus
from backend.src.core.events.base import BaseEvent


class ArchiveUseCases:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def archive_case(self, case_id: str, actor_id: str, tenant_id: str) -> None:
        case = await self.db.get(CaseModel, case_id)
        if not case:
            raise NotFoundError(f"Case {case_id} not found")
        if case.is_archived:
            raise ConflictError("Case is already archived")

        case.is_archived = True
        case.archived_at = datetime.now(timezone.utc)
        case.archived_by = actor_id
        await self.db.commit()

        await event_bus.publish(
            BaseEvent(
                event_name="case.archived",
                tenant_id=tenant_id,
                actor_id=actor_id,
                payload={"case_id": case_id},
            )
        )

    async def restore_case(self, case_id: str, actor_id: str, tenant_id: str) -> None:
        case = await self.db.get(CaseModel, case_id)
        if not case:
            raise NotFoundError(f"Case {case_id} not found")
        if not case.is_archived:
            raise ConflictError("Case is not archived")

        case.is_archived = False
        case.archived_at = None
        case.archived_by = None
        await self.db.commit()

        await event_bus.publish(
            BaseEvent(
                event_name="case.restored",
                tenant_id=tenant_id,
                actor_id=actor_id,
                payload={"case_id": case_id},
            )
        )
