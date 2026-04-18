import uuid
from datetime import datetime, timezone

from sqlalchemy import select, delete
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from backend.src.modules.knowledge_base.infrastructure.models import (
    KBArticleModel,
    KBArticleVersionModel,
    KBTagModel,
    KBArticleTagModel,
    KBReviewEventModel,
    KBFavoriteModel,
    KBFeedbackModel,
    KBDocumentTypeModel,
)
from backend.src.modules.knowledge_base.application.review_workflow import KBWorkflow
from backend.src.core.exceptions import NotFoundError, ForbiddenError
from backend.src.core.events.bus import event_bus
from backend.src.core.events.base import BaseEvent


class KBUseCases:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_article(
        self,
        title: str,
        content_json: dict,
        content_text: str,
        created_by_id: str,
        tenant_id: str | None = None,
        tag_ids: list[str] | None = None,
        document_type_id: str | None = None,
    ) -> KBArticleModel:
        article = KBArticleModel(
            id=str(uuid.uuid4()),
            title=title,
            content_json=content_json,
            content_text=content_text,
            status="draft",
            version=1,
            created_by_id=created_by_id,
            tenant_id=tenant_id,
            document_type_id=document_type_id,
        )
        self.db.add(article)
        await self.db.flush()
        if tag_ids:
            await self._sync_tags(article, tag_ids)
        await self.db.commit()
        await self.db.refresh(article)
        await event_bus.publish(
            BaseEvent(
                event_name="kb.article.created",
                tenant_id=tenant_id or "default",
                actor_id=created_by_id,
                payload={"article_id": article.id},
            )
        )
        return article

    async def update_article(
        self,
        article_id: str,
        user_id: str,
        title: str | None = None,
        content_json: dict | None = None,
        content_text: str | None = None,
        tag_ids: list[str] | None = None,
        document_type_id: str | None = None,
    ) -> KBArticleModel:
        article = await self._get_article(article_id)
        if article.status not in ("draft", "rejected"):
            raise ForbiddenError("Solo se pueden editar artículos en estado draft o rejected")
        # Snapshot inmutable de la versión actual antes de modificar
        snapshot = KBArticleVersionModel(
            id=str(uuid.uuid4()),
            article_id=article.id,
            version_number=article.version,
            title=article.title,
            content_json=article.content_json,
            content_text=article.content_text,
            saved_by_id=user_id,
        )
        self.db.add(snapshot)
        if title is not None:
            article.title = title
        if content_json is not None:
            article.content_json = content_json
        if content_text is not None:
            article.content_text = content_text
        article.version += 1
        if tag_ids is not None:
            await self._sync_tags(article, tag_ids)
        if document_type_id is not None:
            article.document_type_id = document_type_id if document_type_id else None
        await self.db.commit()
        await self.db.refresh(article)
        return article

    async def transition_status(
        self,
        article_id: str,
        actor_id: str,
        to_status: str,
        comment: str | None,
    ) -> KBArticleModel:
        article = await self._get_article(article_id)
        KBWorkflow.validate_transition(article.status, to_status, comment)
        from_status = article.status
        article.status = to_status
        if to_status == "published":
            article.published_at = datetime.now(timezone.utc)
        if to_status == "approved":
            article.approved_by_id = actor_id
        event_record = KBReviewEventModel(
            id=str(uuid.uuid4()),
            article_id=article_id,
            actor_id=actor_id,
            from_status=from_status,
            to_status=to_status,
            comment=comment,
        )
        self.db.add(event_record)
        await self.db.commit()
        await self.db.refresh(article)
        await event_bus.publish(
            BaseEvent(
                event_name="kb.article.status_changed",
                tenant_id=article.tenant_id or "default",
                actor_id=actor_id,
                payload={
                    "article_id": article_id,
                    "from_status": from_status,
                    "to_status": to_status,
                },
            )
        )
        return article

    async def list_articles(
        self,
        status: str | None = None,
        tenant_id: str | None = None,
        tag_slug: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[KBArticleModel]:
        stmt = (
            select(KBArticleModel)
            .where(KBArticleModel.is_deleted.is_(False))
            .options(selectinload(KBArticleModel.tags))
        )
        if status:
            stmt = stmt.where(KBArticleModel.status == status)
        if tenant_id:
            stmt = stmt.where(KBArticleModel.tenant_id == tenant_id)
        if tag_slug:
            stmt = (
                stmt.join(KBArticleTagModel, KBArticleTagModel.article_id == KBArticleModel.id)
                    .join(KBTagModel, KBTagModel.id == KBArticleTagModel.tag_id)
                    .where(KBTagModel.slug == tag_slug)
            )
        stmt = stmt.order_by(KBArticleModel.updated_at.desc()).limit(limit).offset(offset)
        result = await self.db.execute(stmt)
        return list(result.scalars().unique().all())

    async def list_pending_review(
        self, tenant_id: str | None = None, limit: int = 50
    ) -> list[KBArticleModel]:
        stmt = (
            select(KBArticleModel)
            .where(
                KBArticleModel.is_deleted.is_(False),
                KBArticleModel.status == "in_review",
            )
            .options(selectinload(KBArticleModel.tags))
            .order_by(KBArticleModel.updated_at.desc())
            .limit(limit)
        )
        if tenant_id:
            stmt = stmt.where(KBArticleModel.tenant_id == tenant_id)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_article(self, article_id: str) -> KBArticleModel:
        article = await self._get_article(article_id)
        article.view_count += 1
        await self.db.commit()
        return article

    async def toggle_favorite(self, article_id: str, user_id: str) -> bool:
        """Retorna True si se agregó el favorito, False si se eliminó."""
        result = await self.db.execute(
            select(KBFavoriteModel).where(
                KBFavoriteModel.article_id == article_id,
                KBFavoriteModel.user_id == user_id,
            )
        )
        existing = result.scalar_one_or_none()
        if existing:
            await self.db.delete(existing)
            await self.db.commit()
            return False
        fav = KBFavoriteModel(
            id=str(uuid.uuid4()),
            article_id=article_id,
            user_id=user_id,
        )
        self.db.add(fav)
        await self.db.commit()
        return True

    async def get_favorites(self, user_id: str) -> list[KBArticleModel]:
        result = await self.db.execute(
            select(KBArticleModel)
            .join(KBFavoriteModel, KBFavoriteModel.article_id == KBArticleModel.id)
            .where(
                KBFavoriteModel.user_id == user_id,
                KBArticleModel.is_deleted.is_(False),
            )
        )
        return list(result.scalars().all())

    async def submit_feedback(
        self,
        article_id: str,
        user_id: str,
        is_helpful: bool,
        comment: str | None = None,
    ) -> KBFeedbackModel:
        """Upsert: si el usuario ya dio feedback, actualiza contadores y registros."""
        result = await self.db.execute(
            select(KBFeedbackModel).where(
                KBFeedbackModel.article_id == article_id,
                KBFeedbackModel.user_id == user_id,
            )
        )
        existing = result.scalar_one_or_none()
        article = await self._get_article(article_id)

        if existing:
            # Revertir el contador anterior antes de aplicar el nuevo
            if existing.is_helpful:
                article.helpful_count = max(0, article.helpful_count - 1)
            else:
                article.not_helpful_count = max(0, article.not_helpful_count - 1)
            existing.is_helpful = is_helpful
            existing.comment = comment
            fb = existing
        else:
            fb = KBFeedbackModel(
                id=str(uuid.uuid4()),
                article_id=article_id,
                user_id=user_id,
                is_helpful=is_helpful,
                comment=comment,
            )
            self.db.add(fb)

        if is_helpful:
            article.helpful_count += 1
        else:
            article.not_helpful_count += 1

        await self.db.commit()
        await self.db.refresh(fb)
        return fb

    async def check_feedback(self, article_id: str, user_id: str) -> dict:
        """Retorna si el usuario ya dio feedback y cuál fue."""
        result = await self.db.execute(
            select(KBFeedbackModel).where(
                KBFeedbackModel.article_id == article_id,
                KBFeedbackModel.user_id == user_id,
            )
        )
        fb = result.scalar_one_or_none()
        if fb is None:
            return {"has_feedback": False, "is_helpful": None}
        return {"has_feedback": True, "is_helpful": fb.is_helpful}

    async def get_feedback_stats(self, article_id: str) -> dict:
        """Retorna contadores agregados para el artículo."""
        article = await self._get_article(article_id)
        helpful = article.helpful_count
        not_helpful = article.not_helpful_count
        total = helpful + not_helpful
        percentage = 0.0 if total == 0 else round((helpful / total) * 100, 1)
        return {
            "helpful_count": helpful,
            "not_helpful_count": not_helpful,
            "total": total,
            "helpful_percentage": percentage,
        }

    async def get_versions(self, article_id: str) -> list[KBArticleVersionModel]:
        result = await self.db.execute(
            select(KBArticleVersionModel)
            .where(KBArticleVersionModel.article_id == article_id)
            .order_by(KBArticleVersionModel.version_number.desc())
        )
        return list(result.scalars().all())

    async def list_tags(self) -> list[KBTagModel]:
        result = await self.db.execute(select(KBTagModel).order_by(KBTagModel.name))
        return list(result.scalars().all())

    async def create_tag(
        self, name: str, slug: str, tenant_id: str | None = None
    ) -> KBTagModel:
        tag = KBTagModel(
            id=str(uuid.uuid4()),
            name=name,
            slug=slug,
            tenant_id=tenant_id,
        )
        self.db.add(tag)
        await self.db.commit()
        await self.db.refresh(tag)
        return tag

    async def list_document_types(
        self, include_inactive: bool = False
    ) -> list[KBDocumentTypeModel]:
        stmt = select(KBDocumentTypeModel).order_by(
            KBDocumentTypeModel.sort_order, KBDocumentTypeModel.name
        )
        if not include_inactive:
            stmt = stmt.where(KBDocumentTypeModel.is_active.is_(True))
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def create_document_type(
        self, code: str, name: str, icon: str, color: str, sort_order: int = 0
    ) -> KBDocumentTypeModel:
        dt = KBDocumentTypeModel(
            id=str(uuid.uuid4()),
            code=code,
            name=name,
            icon=icon,
            color=color,
            sort_order=sort_order,
            is_active=True,
        )
        self.db.add(dt)
        await self.db.commit()
        await self.db.refresh(dt)
        return dt

    async def update_document_type(
        self,
        document_type_id: str,
        name: str | None = None,
        icon: str | None = None,
        color: str | None = None,
        sort_order: int | None = None,
        is_active: bool | None = None,
    ) -> KBDocumentTypeModel:
        result = await self.db.execute(
            select(KBDocumentTypeModel).where(KBDocumentTypeModel.id == document_type_id)
        )
        dt = result.scalar_one_or_none()
        if not dt:
            raise NotFoundError(f"DocumentType {document_type_id} no encontrado")
        if name is not None:
            dt.name = name
        if icon is not None:
            dt.icon = icon
        if color is not None:
            dt.color = color
        if sort_order is not None:
            dt.sort_order = sort_order
        if is_active is not None:
            dt.is_active = is_active
        await self.db.commit()
        await self.db.refresh(dt)
        return dt

    async def delete_document_type(self, document_type_id: str) -> None:
        """Soft delete: marca is_active=False para preservar integridad."""
        result = await self.db.execute(
            select(KBDocumentTypeModel).where(KBDocumentTypeModel.id == document_type_id)
        )
        dt = result.scalar_one_or_none()
        if not dt:
            raise NotFoundError(f"DocumentType {document_type_id} no encontrado")
        dt.is_active = False
        await self.db.commit()

    async def get_review_history(self, article_id: str) -> dict:
        """Retorna eventos cronológicos + resumen contable por tipo."""
        await self._get_article(article_id)  # valida que exista
        result = await self.db.execute(
            select(KBReviewEventModel)
            .where(KBReviewEventModel.article_id == article_id)
            .order_by(KBReviewEventModel.created_at.asc())
        )
        events = list(result.scalars().all())
        summary = {
            "submitted": 0,
            "approved": 0,
            "rejected": 0,
            "published": 0,
            "returned_to_draft": 0,
        }
        for e in events:
            if e.to_status == "in_review":
                summary["submitted"] += 1
            elif e.to_status == "approved":
                summary["approved"] += 1
            elif e.to_status == "rejected":
                summary["rejected"] += 1
            elif e.to_status == "published":
                summary["published"] += 1
            elif e.to_status == "draft":
                summary["returned_to_draft"] += 1
        return {
            "events": [
                {
                    "id": e.id,
                    "article_id": e.article_id,
                    "actor_id": e.actor_id,
                    "from_status": e.from_status,
                    "to_status": e.to_status,
                    "comment": e.comment,
                    "created_at": e.created_at.isoformat(),
                }
                for e in events
            ],
            "summary": summary,
        }

    async def link_case_to_article(
        self, article_id: str, case_id: str, user_id: str
    ) -> dict:
        """Vincula un caso a un artículo KB. Idempotente.

        Devuelve la fila (existente o nueva) como dict. Si ya existe, retorna
        la fila con su linked_at/linked_by_id original sin actualizar.
        """
        from backend.src.modules.knowledge_base.infrastructure.models import KBArticleCaseModel
        from backend.src.modules.cases.infrastructure.models import CaseModel
        from sqlalchemy.exc import IntegrityError

        # Validar existencia del artículo (reusa método con filtro is_deleted)
        await self._get_article(article_id)

        # Validar existencia del caso
        case_row = await self.db.execute(
            select(CaseModel).where(CaseModel.id == case_id)
        )
        if not case_row.scalar_one_or_none():
            raise NotFoundError(f"Caso {case_id} no encontrado")

        # Intentar insertar; si ya existe, recuperar la fila existente
        link = KBArticleCaseModel(
            article_id=article_id,
            case_id=case_id,
            linked_by_id=user_id,
            linked_at=datetime.now(timezone.utc),
        )
        self.db.add(link)
        try:
            await self.db.commit()
        except IntegrityError:
            await self.db.rollback()
            existing = await self.db.execute(
                select(KBArticleCaseModel).where(
                    KBArticleCaseModel.article_id == article_id,
                    KBArticleCaseModel.case_id == case_id,
                )
            )
            link = existing.scalar_one()

        return {
            "article_id": link.article_id,
            "case_id": link.case_id,
            "linked_at": link.linked_at.isoformat(),
            "linked_by_id": link.linked_by_id,
        }

    async def _get_article(self, article_id: str) -> KBArticleModel:
        result = await self.db.execute(
            select(KBArticleModel)
            .where(KBArticleModel.id == article_id, KBArticleModel.is_deleted.is_(False))
            .options(
                selectinload(KBArticleModel.tags),
                selectinload(KBArticleModel.versions),
            )
        )
        article = result.scalar_one_or_none()
        if not article:
            raise NotFoundError(f"Artículo KB {article_id} no encontrado")
        return article

    async def _sync_tags(self, article: KBArticleModel, tag_ids: list[str]) -> None:
        """Reemplaza los tags del artículo con los nuevos tag_ids."""
        await self.db.execute(
            delete(KBArticleTagModel).where(KBArticleTagModel.article_id == article.id)
        )
        for tag_id in tag_ids:
            self.db.add(
                KBArticleTagModel(
                    id=str(uuid.uuid4()),
                    article_id=article.id,
                    tag_id=tag_id,
                )
            )
