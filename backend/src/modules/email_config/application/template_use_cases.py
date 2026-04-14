import uuid
from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.src.core.exceptions import NotFoundError
from backend.src.modules.email_config.infrastructure.models import EmailTemplateModel


class EmailTemplateUseCases:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_all(self) -> list[EmailTemplateModel]:
        result = await self.db.execute(
            select(EmailTemplateModel).order_by(EmailTemplateModel.scope, EmailTemplateModel.name)
        )
        return list(result.scalars().all())

    async def get(self, template_id: str) -> EmailTemplateModel:
        result = await self.db.execute(
            select(EmailTemplateModel).where(EmailTemplateModel.id == template_id)
        )
        tpl = result.scalar_one_or_none()
        if not tpl:
            raise NotFoundError(f"Email template {template_id} not found")
        return tpl

    async def create(self, name: str, scope: str, blocks: list) -> EmailTemplateModel:
        now = datetime.now(timezone.utc)
        tpl = EmailTemplateModel(
            id=str(uuid.uuid4()), name=name, scope=scope,
            blocks=blocks, is_active=False,
            created_at=now, updated_at=now,
        )
        self.db.add(tpl)
        await self.db.commit()
        await self.db.refresh(tpl)
        return tpl

    async def update(
        self,
        template_id: str,
        name: str | None = None,
        scope: str | None = None,
        blocks: list | None = None,
        is_active: bool | None = None,
    ) -> EmailTemplateModel:
        tpl = await self.get(template_id)
        now = datetime.now(timezone.utc)

        if name is not None:
            tpl.name = name
        if scope is not None:
            tpl.scope = scope
        if blocks is not None:
            tpl.blocks = blocks

        if is_active is True:
            # Deactivate other templates in the same scope
            await self.db.execute(
                update(EmailTemplateModel)
                .where(
                    EmailTemplateModel.scope == tpl.scope,
                    EmailTemplateModel.id != template_id,
                )
                .values(is_active=False, updated_at=now)
            )
            tpl.is_active = True
        elif is_active is False:
            tpl.is_active = False

        tpl.updated_at = now
        await self.db.commit()
        await self.db.refresh(tpl)
        return tpl

    async def delete(self, template_id: str) -> None:
        tpl = await self.get(template_id)
        await self.db.delete(tpl)
        await self.db.commit()

    async def resolve_for_event(self, event_name: str) -> EmailTemplateModel | None:
        """Find active template for the event; fall back to global."""
        result = await self.db.execute(
            select(EmailTemplateModel).where(
                EmailTemplateModel.scope == event_name,
                EmailTemplateModel.is_active.is_(True),
            )
        )
        tpl = result.scalar_one_or_none()
        if tpl:
            return tpl
        result = await self.db.execute(
            select(EmailTemplateModel).where(
                EmailTemplateModel.scope == "global",
                EmailTemplateModel.is_active.is_(True),
            )
        )
        return result.scalar_one_or_none()
