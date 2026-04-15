import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.src.modules.notifications.infrastructure.models import NotificationTemplateModel

# ── Default templates ─────────────────────────────────────────────────────────

DEFAULT_TEMPLATES = [
    {
        "event_name": "case.assigned",
        "notification_type": "case_assigned",
        "title": "Caso asignado: {case_number}",
        "body": "{assigned_by} te asignó el caso {case_number} — {case_title}",
        "variables": ["case_number", "case_title", "assigned_by"],
    },
    {
        "event_name": "case.status_changed",
        "notification_type": "case_updated",
        "title": "Estado actualizado: {case_number}",
        "body": "El caso {case_number} cambió de {from_status} a {to_status}",
        "variables": ["case_number", "case_title", "from_status", "to_status"],
    },
    {
        "event_name": "case.updated",
        "notification_type": "case_updated",
        "title": "Caso actualizado: {case_number}",
        "body": "{updated_by} realizó cambios en el caso {case_number} — {case_title}",
        "variables": ["case_number", "case_title", "updated_by"],
    },
    {
        "event_name": "sla.breached",
        "notification_type": "sla_breach",
        "title": "SLA vencido: {case_number}",
        "body": "El caso {case_number} — {case_title} superó el tiempo límite de resolución",
        "variables": ["case_number", "case_title"],
    },
    {
        "event_name": "kb.review_requested",
        "notification_type": "kb_review_request",
        "title": "Artículo en revisión",
        "body": '{requested_by} envió "{article_title}" para revisión',
        "variables": ["article_title", "requested_by"],
    },
    {
        "event_name": "mention",
        "notification_type": "mention",
        "title": "Te mencionaron en {case_number}",
        "body": "{mentioned_by} te mencionó en el caso {case_number}",
        "variables": ["case_number", "mentioned_by"],
    },
]


# ── Use cases ─────────────────────────────────────────────────────────────────

class NotificationTemplateUseCases:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def seed_defaults(self) -> None:
        """Insert default templates that don't exist yet. Safe to call multiple times."""
        now = datetime.now(timezone.utc)
        for tpl in DEFAULT_TEMPLATES:
            exists = await self.db.execute(
                select(NotificationTemplateModel).where(
                    NotificationTemplateModel.event_name == tpl["event_name"]
                )
            )
            if exists.scalar_one_or_none() is None:
                self.db.add(
                    NotificationTemplateModel(
                        id=str(uuid.uuid4()),
                        event_name=tpl["event_name"],
                        notification_type=tpl["notification_type"],
                        title=tpl["title"],
                        body=tpl["body"],
                        is_enabled=True,
                        variables=tpl["variables"],
                        created_at=now,
                        updated_at=now,
                    )
                )
        await self.db.commit()

    async def list_all(self) -> list[NotificationTemplateModel]:
        await self.seed_defaults()
        result = await self.db.execute(
            select(NotificationTemplateModel).order_by(NotificationTemplateModel.event_name)
        )
        return list(result.scalars().all())

    async def get_by_event(self, event_name: str) -> NotificationTemplateModel | None:
        result = await self.db.execute(
            select(NotificationTemplateModel).where(
                NotificationTemplateModel.event_name == event_name
            )
        )
        return result.scalar_one_or_none()

    async def update(
        self,
        template_id: str,
        title: str | None = None,
        body: str | None = None,
        is_enabled: bool | None = None,
    ) -> NotificationTemplateModel:
        result = await self.db.execute(
            select(NotificationTemplateModel).where(
                NotificationTemplateModel.id == template_id
            )
        )
        tpl = result.scalar_one_or_none()
        if not tpl:
            from backend.src.core.exceptions import NotFoundError
            raise NotFoundError(f"Template {template_id} not found")

        if title is not None:
            tpl.title = title
        if body is not None:
            tpl.body = body
        if is_enabled is not None:
            tpl.is_enabled = is_enabled
        tpl.updated_at = datetime.now(timezone.utc)
        await self.db.commit()
        await self.db.refresh(tpl)
        return tpl

    async def reset_to_default(self, template_id: str) -> NotificationTemplateModel:
        """Restore a template's title and body to system defaults."""
        result = await self.db.execute(
            select(NotificationTemplateModel).where(
                NotificationTemplateModel.id == template_id
            )
        )
        tpl = result.scalar_one_or_none()
        if not tpl:
            from backend.src.core.exceptions import NotFoundError
            raise NotFoundError(f"Template {template_id} not found")

        default = next((d for d in DEFAULT_TEMPLATES if d["event_name"] == tpl.event_name), None)
        if default:
            tpl.title = default["title"]
            tpl.body = default["body"]
            tpl.updated_at = datetime.now(timezone.utc)
            await self.db.commit()
            await self.db.refresh(tpl)
        return tpl
