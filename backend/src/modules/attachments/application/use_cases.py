import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.src.modules.attachments.infrastructure.models import CaseAttachmentModel
from backend.src.modules.attachments.application.storage import (
    detect_mime_type,
    generate_stored_filename,
    save_file,
    ALLOWED_MIME_TYPES,
    MAX_FILE_SIZE,
)
from backend.src.core.exceptions import ValidationError, NotFoundError, ForbiddenError
from backend.src.core.events.bus import event_bus
from backend.src.core.events.base import BaseEvent


class AttachmentUseCases:
    def __init__(self, db: AsyncSession, upload_dir: str):
        self.db = db
        self.upload_dir = upload_dir

    async def upload(
        self, case_id: str, user_id: str, tenant_id: str | None, file
    ) -> CaseAttachmentModel:
        content = await file.read()
        if len(content) > MAX_FILE_SIZE:
            raise ValidationError(
                f"Excede el tamaño máximo de {MAX_FILE_SIZE // 1024 // 1024}MB"
            )

        real_mime = detect_mime_type(content)
        if real_mime not in ALLOWED_MIME_TYPES:
            raise ValidationError(f"Tipo de archivo no permitido: {real_mime}")

        stored_name = generate_stored_filename(file.filename)
        file_path = await save_file(content, stored_name, case_id, self.upload_dir)

        attachment = CaseAttachmentModel(
            id=str(uuid.uuid4()),
            case_id=case_id,
            user_id=user_id,
            tenant_id=tenant_id,
            original_filename=file.filename,
            stored_filename=stored_name,
            file_path=file_path,
            mime_type=real_mime,
            file_size=len(content),
        )
        self.db.add(attachment)
        await self.db.commit()
        await self.db.refresh(attachment)

        await event_bus.publish(
            BaseEvent(
                event_name="attachment.uploaded",
                tenant_id=tenant_id or "default",
                actor_id=user_id,
                payload={
                    "case_id": case_id,
                    "attachment_id": attachment.id,
                    "filename": file.filename,
                },
            )
        )
        return attachment

    async def list_for_case(self, case_id: str) -> list[CaseAttachmentModel]:
        result = await self.db.execute(
            select(CaseAttachmentModel)
            .where(
                CaseAttachmentModel.case_id == case_id,
                CaseAttachmentModel.is_deleted == False,
            )
            .order_by(CaseAttachmentModel.created_at.desc())
        )
        return list(result.scalars().all())

    async def delete(
        self, attachment_id: str, user_id: str, is_admin: bool = False
    ) -> None:
        att = await self.db.get(CaseAttachmentModel, attachment_id)
        if not att:
            raise NotFoundError(f"Adjunto {attachment_id} no encontrado")
        if att.user_id != user_id and not is_admin:
            raise ForbiddenError("Sin permiso para eliminar este adjunto")
        att.is_deleted = True
        await self.db.commit()
