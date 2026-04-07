from datetime import datetime, timezone

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.src.core.exceptions import ForbiddenError, NotFoundError
from backend.src.modules.notifications.infrastructure.models import NotificationModel


class NotificationUseCases:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(
        self,
        user_id: str,
        title: str,
        body: str,
        notification_type: str,
        reference_id: str | None = None,
        reference_type: str | None = None,
        tenant_id: str | None = None,
    ) -> NotificationModel:
        notif = NotificationModel(
            user_id=user_id,
            title=title,
            body=body,
            notification_type=notification_type,
            reference_id=reference_id,
            reference_type=reference_type,
            tenant_id=tenant_id,
        )
        self.db.add(notif)
        await self.db.flush()
        await self.db.refresh(notif)
        return notif

    async def list_for_user(
        self, user_id: str, unread_only: bool = False, limit: int = 30
    ) -> list[NotificationModel]:
        stmt = (
            select(NotificationModel)
            .where(NotificationModel.user_id == user_id)
            .order_by(NotificationModel.created_at.desc())
            .limit(limit)
        )
        if unread_only:
            stmt = stmt.where(NotificationModel.is_read.is_(False))
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def mark_read(self, notification_id: str, user_id: str) -> None:
        result = await self.db.execute(
            select(NotificationModel).where(NotificationModel.id == notification_id)
        )
        notif = result.scalar_one_or_none()
        if not notif:
            raise NotFoundError(f"Notificación {notification_id} no encontrada")
        if notif.user_id != user_id:
            raise ForbiddenError("Sin permiso para marcar esta notificación")
        notif.is_read = True
        notif.read_at = datetime.now(timezone.utc)
        await self.db.flush()

    async def mark_all_read(self, user_id: str) -> int:
        result = await self.db.execute(
            update(NotificationModel)
            .where(NotificationModel.user_id == user_id, NotificationModel.is_read.is_(False))
            .values(is_read=True, read_at=datetime.now(timezone.utc))
        )
        return result.rowcount

    async def get_unread_count(self, user_id: str) -> int:
        result = await self.db.execute(
            select(func.count()).where(
                NotificationModel.user_id == user_id,
                NotificationModel.is_read.is_(False),
            )
        )
        return result.scalar() or 0
