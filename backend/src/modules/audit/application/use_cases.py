from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.src.modules.audit.infrastructure.models import AuditLogModel


class AuditUseCases:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_logs(
        self,
        entity_type: str | None = None,
        entity_id: str | None = None,
        actor_id: str | None = None,
        action: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[AuditLogModel]:
        stmt = select(AuditLogModel).order_by(AuditLogModel.created_at.desc())
        if entity_type:
            stmt = stmt.where(AuditLogModel.entity_type == entity_type)
        if entity_id:
            stmt = stmt.where(AuditLogModel.entity_id == entity_id)
        if actor_id:
            stmt = stmt.where(AuditLogModel.actor_id == actor_id)
        if action:
            stmt = stmt.where(AuditLogModel.action == action)
        stmt = stmt.limit(limit).offset(offset)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())
