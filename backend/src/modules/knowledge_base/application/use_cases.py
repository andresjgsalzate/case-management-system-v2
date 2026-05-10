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
    KBArticleCaseModel,
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
        visibility: str = "private",
    ) -> KBArticleModel:
        # Si el creador pide 'public' al crear, lo dejamos como 'private'
        # con pending_visibility='public' y forzamos pasar por workflow al
        # publicar. En la creación inicial el status es draft, así que el
        # workflow se dispara al solicitar publicación.
        initial_visibility = visibility if visibility in ("private", "team") else "private"
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
            visibility=initial_visibility,
            pending_visibility="public" if visibility == "public" else None,
        )
        self.db.add(article)
        await self.db.flush()
        if tag_ids:
            await self._sync_tags(article, tag_ids)
        await self.db.commit()
        # Re-fetch con selectinload para que el serializer pueda acceder a
        # `tags` / `created_by` sin disparar lazy-load (rompería en async).
        article = await self._get_article(article.id)
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
        visibility: str | None = None,
    ) -> KBArticleModel:
        article = await self._get_article(article_id)
        # Si SOLO se está cambiando visibility (sin tocar contenido), permitir
        # incluso si el artículo ya está publicado. Si se tocan contenido/título,
        # mantener la regla original.
        only_visibility = (
            title is None and content_json is None and content_text is None
            and tag_ids is None and document_type_id is None
            and visibility is not None
        )
        # Bloquear edits mientras un revisor está mirando el artículo (race condition).
        if not only_visibility and article.status == "in_review":
            raise ForbiddenError("No se puede editar un artículo en revisión")
        # Editar un artículo aprobado o publicado lo regresa al ciclo: vuelve a
        # `draft` y debe re-enviarse a revisión para volver a publicarse.
        revert_to_draft = (
            not only_visibility and article.status in ("approved", "published")
        )
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
        if visibility is not None and visibility != article.visibility:
            if visibility not in ("private", "team", "public"):
                raise ForbiddenError(f"Visibilidad inválida: {visibility}")
            if visibility == "public":
                # Subir a público requiere aprobación → guarda como pendiente
                # y manda a revisión solo si el artículo está publicado/aprobado.
                # Si el artículo está en draft/rejected, deja la pendiente y la
                # publicación normal recogerá el flag cuando se apruebe.
                article.pending_visibility = "public"
                if article.status in ("approved", "published"):
                    article.status = "in_review"
            else:
                # Bajar a private/team es inmediato, no requiere aprobación.
                article.visibility = visibility
                # Si había pending de public, se cancela la solicitud.
                article.pending_visibility = None
        # Aplicar el revert al final: si era approved/published, el edit lo
        # devuelve a draft. Pisa cualquier cambio de status hecho por la lógica
        # de visibility de arriba — preferimos que el autor recorra el ciclo
        # completo (draft → in_review → approved → published).
        if revert_to_draft:
            article.status = "draft"
        await self.db.commit()
        # Re-fetch para refrescar la collection `tags` tras `_sync_tags`
        # (que hace DELETE/INSERT directo y deja la collection en memoria stale).
        article = await self._get_article(article.id)
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
            # Aplicar el cambio de visibilidad pendiente si lo hay
            if article.pending_visibility:
                article.visibility = article.pending_visibility
                article.pending_visibility = None
        if to_status == "approved":
            article.approved_by_id = actor_id
        if to_status == "rejected":
            # El revisor rechazó — descartar cualquier cambio de visibilidad pendiente
            article.pending_visibility = None
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
        user=None,
    ) -> list[KBArticleModel]:
        stmt = (
            select(KBArticleModel)
            .where(KBArticleModel.is_deleted.is_(False))
            .options(
                selectinload(KBArticleModel.tags).selectinload(KBArticleTagModel.tag),
                selectinload(KBArticleModel.created_by),
                selectinload(KBArticleModel.kb_article_cases).selectinload(KBArticleCaseModel.case_ref),
            )
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
        if user is not None:
            stmt = self._filter_by_visibility(stmt, user)
        stmt = stmt.order_by(KBArticleModel.updated_at.desc()).limit(limit).offset(offset)
        result = await self.db.execute(stmt)
        return list(result.scalars().unique().all())

    def _filter_by_visibility(self, stmt, user):
        """Aplica reglas de visibilidad al SELECT según el usuario actual.

        Reglas:
          - scope='all' (Admin/Super Admin): ve todo, sin filtro.
          - scope!='all':
            * visibility='public' → todos lo ven.
            * visibility='team' → solo si created_by está en su mismo team_id.
            * visibility='private' → solo si created_by = el propio user_id.
        """
        from sqlalchemy import or_, and_
        from backend.src.modules.users.infrastructure.models import UserModel

        scope = getattr(user, "scope", "own")
        if scope == "all":
            return stmt

        user_id = getattr(user, "user_id", None)
        team_id = getattr(user, "team_id", None)

        # Necesitamos el team del creador para chequear "team visibility"
        creator = UserModel.__table__.alias("creator_u")
        stmt = stmt.outerjoin(creator, creator.c.id == KBArticleModel.created_by_id)

        clauses = [
            KBArticleModel.visibility == "public",
            and_(KBArticleModel.visibility == "private", KBArticleModel.created_by_id == user_id),
        ]
        if team_id:
            clauses.append(
                and_(KBArticleModel.visibility == "team", creator.c.team_id == team_id)
            )
        return stmt.where(or_(*clauses))

    async def list_pending_review(
        self, tenant_id: str | None = None, limit: int = 50
    ) -> list[KBArticleModel]:
        stmt = (
            select(KBArticleModel)
            .where(
                KBArticleModel.is_deleted.is_(False),
                KBArticleModel.status == "in_review",
            )
            .options(
                selectinload(KBArticleModel.tags).selectinload(KBArticleTagModel.tag),
                selectinload(KBArticleModel.created_by),
                selectinload(KBArticleModel.kb_article_cases).selectinload(KBArticleCaseModel.case_ref),
            )
            .order_by(KBArticleModel.updated_at.desc())
            .limit(limit)
        )
        if tenant_id:
            stmt = stmt.where(KBArticleModel.tenant_id == tenant_id)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_article(self, article_id: str, user=None) -> KBArticleModel:
        article = await self._get_article(article_id)
        if user is not None:
            await self._enforce_visibility(article, user)
        article.view_count += 1
        await self.db.commit()
        return article

    async def _enforce_visibility(self, article: KBArticleModel, user) -> None:
        """Lanza ForbiddenError si el usuario no puede ver el artículo según
        las reglas de visibility.

        Reglas:
          - scope='all' → siempre ve.
          - public → todos lo ven.
          - private → solo el autor.
          - team → autor o usuario del mismo team que el autor.
        """
        scope = getattr(user, "scope", "own")
        if scope == "all":
            return
        if article.visibility == "public":
            return
        user_id = getattr(user, "user_id", None)
        if article.created_by_id == user_id:
            return  # el autor siempre lo ve
        if article.visibility == "team":
            from backend.src.modules.users.infrastructure.models import UserModel
            res = await self.db.execute(
                select(UserModel.team_id).where(UserModel.id == article.created_by_id)
            )
            creator_team = res.scalar_one_or_none()
            user_team = getattr(user, "team_id", None)
            if creator_team and user_team and creator_team == user_team:
                return
        # private (no autor) o team (sin coincidencia) → denegar
        raise ForbiddenError("No tienes permiso para ver este artículo")

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

    async def list_popular_tags(
        self, limit: int = 10, tenant_id: str | None = None
    ) -> list[dict]:
        """Top N tags más usados, ordenados por número de artículos no eliminados
        que los usan (cualquier estado excepto is_deleted=true).

        Devuelve dicts con id/name/slug/usage_count para que el router serialice
        sin tocar el modelo ORM directamente."""
        from sqlalchemy import func

        stmt = (
            select(
                KBTagModel.id,
                KBTagModel.name,
                KBTagModel.slug,
                func.count(KBArticleTagModel.article_id).label("usage_count"),
            )
            .join(KBArticleTagModel, KBArticleTagModel.tag_id == KBTagModel.id)
            .join(KBArticleModel, KBArticleModel.id == KBArticleTagModel.article_id)
            .where(KBArticleModel.is_deleted.is_(False))
            .group_by(KBTagModel.id, KBTagModel.name, KBTagModel.slug)
            .order_by(func.count(KBArticleTagModel.article_id).desc(), KBTagModel.name.asc())
            .limit(limit)
        )
        if tenant_id:
            stmt = stmt.where(KBTagModel.tenant_id == tenant_id)
        result = await self.db.execute(stmt)
        return [
            {"id": r.id, "name": r.name, "slug": r.slug, "usage_count": r.usage_count}
            for r in result.all()
        ]

    async def create_tag(
        self, name: str, slug: str, tenant_id: str | None = None
    ) -> KBTagModel:
        """Crea un tag KB. Si ya existe uno con el mismo nombre case-insensitive
        (o el mismo slug), retorna el existente — idempotente. Esto evita
        duplicados como 'Pruebas', 'PRUEBAS', 'PrueBas' que comparten slug."""
        from sqlalchemy import func, or_

        normalized_name = name.strip()
        existing = await self.db.execute(
            select(KBTagModel).where(
                or_(
                    func.lower(KBTagModel.name) == normalized_name.lower(),
                    KBTagModel.slug == slug,
                )
            )
        )
        existing_tag = existing.scalar_one_or_none()
        if existing_tag:
            return existing_tag

        tag = KBTagModel(
            id=str(uuid.uuid4()),
            name=normalized_name,
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

        # Validar existencia del caso. No se filtra `is_archived` — la relación es
        # metadata documental (spec §2), no una bifurcación de seguridad, y debe
        # permitir vincular artículos KB a casos archivados para documentación histórica.
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

    async def unlink_case_from_article(self, article_id: str, case_id: str) -> None:
        """Elimina la relación artículo↔caso. Idempotente (si no existe, no es error)."""
        from backend.src.modules.knowledge_base.infrastructure.models import KBArticleCaseModel

        await self.db.execute(
            delete(KBArticleCaseModel).where(
                KBArticleCaseModel.article_id == article_id,
                KBArticleCaseModel.case_id == case_id,
            )
        )
        await self.db.commit()

    async def list_article_cases(
        self, article_id: str, can_access_cases: bool
    ) -> list[dict]:
        """Devuelve los casos vinculados a un artículo, enriquecidos.

        `can_access_cases` viene del router tras verificar el permiso cases:read.
        Se propaga igual a todas las filas — hoy el chequeo es global. Si en
        el futuro se introduce scope por caso/equipo, este es el punto único
        de cambio.
        """
        from backend.src.modules.knowledge_base.infrastructure.models import KBArticleCaseModel
        from backend.src.modules.cases.infrastructure.models import CaseModel

        await self._get_article(article_id)  # valida existencia

        result = await self.db.execute(
            select(KBArticleCaseModel, CaseModel)
            .join(CaseModel, CaseModel.id == KBArticleCaseModel.case_id)
            .where(KBArticleCaseModel.article_id == article_id)
            .order_by(KBArticleCaseModel.linked_at.desc())
        )
        rows = result.all()
        return [
            {
                "case_id": link.case_id,
                "case_number": case.case_number,
                "case_title": case.title,
                "linked_at": link.linked_at.isoformat(),
                "can_access": can_access_cases,
            }
            for link, case in rows
        ]

    async def list_case_articles(self, case_id: str, user=None) -> list[dict]:
        """Devuelve los artículos KB vinculados a un caso.

        No filtra por status — un caso puede mostrar drafts/in_review vinculados
        si el usuario tiene visibility para verlos. El filtro real de "qué puedo
        ver" lo hace `_filter_by_visibility`.
        """
        from backend.src.modules.knowledge_base.infrastructure.models import KBArticleCaseModel

        stmt = (
            select(KBArticleCaseModel, KBArticleModel)
            .join(KBArticleModel, KBArticleModel.id == KBArticleCaseModel.article_id)
            .where(
                KBArticleCaseModel.case_id == case_id,
                KBArticleModel.is_deleted.is_(False),
            )
            .options(selectinload(KBArticleModel.document_type))
            .order_by(KBArticleCaseModel.linked_at.desc())
        )
        if user is not None:
            stmt = self._filter_by_visibility(stmt, user)
        result = await self.db.execute(stmt)
        rows = result.all()
        return [
            {
                "id": article.id,
                "title": article.title,
                "status": article.status,
                "document_type": (
                    {
                        "id": article.document_type.id,
                        "code": article.document_type.code,
                        "name": article.document_type.name,
                        "icon": article.document_type.icon,
                        "color": article.document_type.color,
                    }
                    if article.document_type
                    else None
                ),
                "linked_at": link.linked_at.isoformat(),
            }
            for link, article in rows
        ]

    async def _get_article(self, article_id: str) -> KBArticleModel:
        result = await self.db.execute(
            select(KBArticleModel)
            .where(KBArticleModel.id == article_id, KBArticleModel.is_deleted.is_(False))
            .options(
                # Carga anidada: tags (puentes) → cada puente carga su .tag
                selectinload(KBArticleModel.tags).selectinload(KBArticleTagModel.tag),
                selectinload(KBArticleModel.versions),
                selectinload(KBArticleModel.created_by),
                selectinload(KBArticleModel.kb_article_cases).selectinload(KBArticleCaseModel.case_ref),
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
