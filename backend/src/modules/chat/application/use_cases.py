import uuid
from datetime import datetime, timezone, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.src.modules.chat.infrastructure.models import ChatMessageModel, ChatMessageEditModel
from backend.src.core.exceptions import NotFoundError, ForbiddenError, BusinessRuleError
from backend.src.core.events.bus import event_bus
from backend.src.core.events.base import BaseEvent

EDIT_WINDOW_MINUTES = 15


class ChatUseCases:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def send_message(
        self,
        case_id: str,
        user_id: str,
        tenant_id: str | None,
        content: str,
        content_type: str = "text",
        attachment_id: str | None = None,
    ) -> ChatMessageModel:
        msg = ChatMessageModel(
            id=str(uuid.uuid4()),
            case_id=case_id,
            user_id=user_id,
            tenant_id=tenant_id,
            content=content,
            content_type=content_type,
            attachment_id=attachment_id,
        )
        self.db.add(msg)
        await self.db.commit()
        await self.db.refresh(msg)

        await event_bus.publish(
            BaseEvent(
                event_name="chat.message.sent",
                tenant_id=tenant_id or "default",
                actor_id=user_id,
                payload={"case_id": case_id, "message_id": msg.id},
            )
        )
        return msg

    async def list_messages(
        self, case_id: str, limit: int = 50, offset: int = 0
    ) -> list[ChatMessageModel]:
        result = await self.db.execute(
            select(ChatMessageModel)
            .where(ChatMessageModel.case_id == case_id)
            .order_by(ChatMessageModel.created_at.asc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def edit_message(
        self, message_id: str, user_id: str, new_content: str
    ) -> ChatMessageModel:
        msg = await self._get_message(message_id)
        if msg.user_id != user_id:
            raise ForbiddenError("Solo el autor puede editar este mensaje")

        now = datetime.now(timezone.utc)
        created = msg.created_at
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        if (now - created) > timedelta(minutes=EDIT_WINDOW_MINUTES):
            raise BusinessRuleError(
                f"Fuera de la ventana de edición ({EDIT_WINDOW_MINUTES} minutos)"
            )

        edit = ChatMessageEditModel(
            id=str(uuid.uuid4()),
            message_id=message_id,
            previous_content=msg.content,
            edited_by_id=user_id,
        )
        self.db.add(edit)
        msg.content = new_content
        msg.is_edited = True
        await self.db.commit()
        await self.db.refresh(msg)

        await event_bus.publish(
            BaseEvent(
                event_name="chat.message.edited",
                tenant_id=msg.tenant_id or "default",
                actor_id=user_id,
                payload={"case_id": msg.case_id, "message_id": message_id},
            )
        )
        return msg

    async def delete_message(self, message_id: str, user_id: str) -> None:
        msg = await self._get_message(message_id)
        if msg.user_id != user_id:
            raise ForbiddenError("Solo el autor puede eliminar este mensaje")
        msg.content = "Mensaje eliminado"
        msg.is_deleted = True
        await self.db.commit()

        await event_bus.publish(
            BaseEvent(
                event_name="chat.message.deleted",
                tenant_id=msg.tenant_id or "default",
                actor_id=user_id,
                payload={"case_id": msg.case_id, "message_id": message_id},
            )
        )

    async def _get_message(self, message_id: str) -> ChatMessageModel:
        result = await self.db.execute(
            select(ChatMessageModel).where(ChatMessageModel.id == message_id)
        )
        msg = result.scalar_one_or_none()
        if not msg:
            raise NotFoundError(f"Mensaje {message_id} no encontrado")
        return msg
