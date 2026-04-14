import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.src.modules.notes.infrastructure.models import CaseNoteModel
from backend.src.core.exceptions import NotFoundError, ForbiddenError
from backend.src.core.events.bus import event_bus
from backend.src.core.events.base import BaseEvent


class NoteUseCases:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(
        self, case_id: str, user_id: str, tenant_id: str | None, content: str
    ) -> CaseNoteModel:
        note = CaseNoteModel(
            id=str(uuid.uuid4()),
            case_id=case_id,
            user_id=user_id,
            tenant_id=tenant_id,
            content=content,
        )
        self.db.add(note)
        await self.db.commit()
        await self.db.refresh(note)
        await event_bus.publish(
            BaseEvent(
                event_name="note.created",
                tenant_id=tenant_id or "default",
                actor_id=user_id,
                payload={"case_id": case_id, "note_id": note.id},
            )
        )
        return note

    async def list_for_case(self, case_id: str) -> list[CaseNoteModel]:
        result = await self.db.execute(
            select(CaseNoteModel)
            .options(selectinload(CaseNoteModel.author))
            .where(CaseNoteModel.case_id == case_id, CaseNoteModel.is_deleted == False)
            .order_by(CaseNoteModel.created_at.desc())
        )
        return list(result.scalars().all())

    async def update(self, note_id: str, user_id: str, content: str) -> CaseNoteModel:
        note = await self._get(note_id)
        if note.user_id != user_id:
            raise ForbiddenError("Solo el autor puede editar esta nota")
        note.content = content
        await self.db.commit()
        await self.db.refresh(note)
        return note

    async def delete(self, note_id: str, user_id: str) -> None:
        note = await self._get(note_id)
        if note.user_id != user_id:
            raise ForbiddenError("Solo el autor puede eliminar esta nota")
        note.is_deleted = True
        await self.db.commit()

    async def _get(self, note_id: str) -> CaseNoteModel:
        result = await self.db.execute(
            select(CaseNoteModel).where(CaseNoteModel.id == note_id)
        )
        note = result.scalar_one_or_none()
        if not note:
            raise NotFoundError(f"Nota {note_id} no encontrada")
        return note
