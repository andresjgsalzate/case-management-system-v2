from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from typing import Any

from backend.src.core.dependencies import DBSession
from backend.src.core.responses import SuccessResponse
from backend.src.core.middleware.permission_checker import CurrentUser, PermissionChecker
from backend.src.modules.knowledge_base.application.use_cases import KBUseCases

router = APIRouter(prefix="/api/v1/kb", tags=["knowledge_base"])
KBRead = Depends(PermissionChecker("knowledge_base", "read"))
KBCreate = Depends(PermissionChecker("knowledge_base", "create"))
KBManage = Depends(PermissionChecker("knowledge_base", "manage"))
DocTypeRead = Depends(PermissionChecker("document_types", "read"))
DocTypeCreate = Depends(PermissionChecker("document_types", "create"))
DocTypeUpdate = Depends(PermissionChecker("document_types", "update"))
DocTypeDelete = Depends(PermissionChecker("document_types", "delete"))


class TagCreateDTO(BaseModel):
    name: str
    slug: str


class ArticleCreateDTO(BaseModel):
    title: str
    content_json: dict[str, Any]
    content_text: str
    tag_ids: list[str] = []
    document_type_id: str | None = None


class ArticleUpdateDTO(BaseModel):
    title: str | None = None
    content_json: dict[str, Any] | None = None
    content_text: str | None = None
    tag_ids: list[str] | None = None
    document_type_id: str | None = None


class TransitionDTO(BaseModel):
    to_status: str
    comment: str | None = None


class FeedbackDTO(BaseModel):
    is_helpful: bool
    comment: str | None = None


class DocumentTypeCreateDTO(BaseModel):
    code: str
    name: str
    icon: str
    color: str
    sort_order: int = 0


class DocumentTypeUpdateDTO(BaseModel):
    name: str | None = None
    icon: str | None = None
    color: str | None = None
    sort_order: int | None = None
    is_active: bool | None = None


# ── Tags ──────────────────────────────────────────────────────────────────────

@router.get("/tags", response_model=SuccessResponse[list[dict]])
async def list_tags(
    db: DBSession,
    current_user: CurrentUser = KBRead,
):
    uc = KBUseCases(db=db)
    tags = await uc.list_tags()
    return SuccessResponse.ok([{"id": t.id, "name": t.name, "slug": t.slug} for t in tags])


@router.post("/tags", status_code=201)
async def create_tag(
    body: TagCreateDTO,
    db: DBSession,
    current_user: CurrentUser = KBCreate,
):
    uc = KBUseCases(db=db)
    tag = await uc.create_tag(
        name=body.name,
        slug=body.slug,
        tenant_id=current_user.tenant_id,
    )
    return SuccessResponse.ok({"id": tag.id, "name": tag.name, "slug": tag.slug})


# ── Articles ──────────────────────────────────────────────────────────────────

@router.get("/articles", response_model=SuccessResponse[list[dict]])
async def list_articles(
    db: DBSession,
    status: str | None = Query(default=None),
    tag_slug: str | None = Query(default=None),
    limit: int = Query(default=20, le=100),
    offset: int = Query(default=0),
    current_user: CurrentUser = KBRead,
):
    uc = KBUseCases(db=db)
    articles = await uc.list_articles(
        status=status,
        tenant_id=current_user.tenant_id,
        tag_slug=tag_slug,
        limit=limit,
        offset=offset,
    )
    return SuccessResponse.ok([_serialize_article(a) for a in articles])


@router.post("/articles", status_code=201)
async def create_article(
    body: ArticleCreateDTO,
    db: DBSession,
    current_user: CurrentUser = KBCreate,
):
    uc = KBUseCases(db=db)
    article = await uc.create_article(
        title=body.title,
        content_json=body.content_json,
        content_text=body.content_text,
        created_by_id=current_user.user_id,
        tenant_id=current_user.tenant_id,
        tag_ids=body.tag_ids or None,
        document_type_id=body.document_type_id,
    )
    return SuccessResponse.ok(_serialize_article(article))


@router.get("/articles/pending-review", response_model=SuccessResponse[list[dict]])
async def list_pending_review(
    db: DBSession,
    current_user: CurrentUser = KBManage,
):
    uc = KBUseCases(db=db)
    articles = await uc.list_pending_review(tenant_id=current_user.tenant_id)
    return SuccessResponse.ok([_serialize_article(a) for a in articles])


@router.get("/articles/{article_id}")
async def get_article(
    article_id: str,
    db: DBSession,
    current_user: CurrentUser = KBRead,
):
    uc = KBUseCases(db=db)
    article = await uc.get_article(article_id=article_id)
    return SuccessResponse.ok(_serialize_article(article))


@router.patch("/articles/{article_id}")
async def update_article(
    article_id: str,
    body: ArticleUpdateDTO,
    db: DBSession,
    current_user: CurrentUser = KBCreate,
):
    uc = KBUseCases(db=db)
    article = await uc.update_article(
        article_id=article_id,
        user_id=current_user.user_id,
        title=body.title,
        content_json=body.content_json,
        content_text=body.content_text,
        tag_ids=body.tag_ids,
        document_type_id=body.document_type_id,
    )
    return SuccessResponse.ok(_serialize_article(article))


@router.post("/articles/{article_id}/transitions")
async def transition_article(
    article_id: str,
    body: TransitionDTO,
    db: DBSession,
    current_user: CurrentUser = KBManage,
):
    uc = KBUseCases(db=db)
    article = await uc.transition_status(
        article_id=article_id,
        actor_id=current_user.user_id,
        to_status=body.to_status,
        comment=body.comment,
    )
    return SuccessResponse.ok(_serialize_article(article))


@router.get("/articles/{article_id}/versions")
async def get_versions(
    article_id: str,
    db: DBSession,
    current_user: CurrentUser = KBRead,
):
    uc = KBUseCases(db=db)
    versions = await uc.get_versions(article_id=article_id)
    return SuccessResponse.ok([
        {
            "id": v.id,
            "version_number": v.version_number,
            "title": v.title,
            "content_text": v.content_text,
            "saved_by_id": v.saved_by_id,
            "created_at": v.created_at.isoformat(),
        }
        for v in versions
    ])


@router.get("/articles/{article_id}/review-history")
async def get_review_history(
    article_id: str,
    db: DBSession,
    current_user: CurrentUser = KBRead,
):
    uc = KBUseCases(db=db)
    history = await uc.get_review_history(article_id=article_id)
    return SuccessResponse.ok(history)


@router.post("/articles/{article_id}/feedback")
async def submit_feedback(
    article_id: str,
    body: FeedbackDTO,
    db: DBSession,
    current_user: CurrentUser = KBRead,
):
    uc = KBUseCases(db=db)
    fb = await uc.submit_feedback(
        article_id=article_id,
        user_id=current_user.user_id,
        is_helpful=body.is_helpful,
        comment=body.comment,
    )
    return SuccessResponse.ok({"id": fb.id, "is_helpful": fb.is_helpful})


@router.get("/articles/{article_id}/feedback/check")
async def check_feedback(
    article_id: str,
    db: DBSession,
    current_user: CurrentUser = KBRead,
):
    uc = KBUseCases(db=db)
    result = await uc.check_feedback(
        article_id=article_id, user_id=current_user.user_id
    )
    return SuccessResponse.ok(result)


@router.get("/articles/{article_id}/feedback/stats")
async def get_feedback_stats(
    article_id: str,
    db: DBSession,
    current_user: CurrentUser = KBRead,
):
    uc = KBUseCases(db=db)
    stats = await uc.get_feedback_stats(article_id=article_id)
    return SuccessResponse.ok(stats)


@router.post("/articles/{article_id}/favorite")
async def toggle_favorite(
    article_id: str,
    db: DBSession,
    current_user: CurrentUser = KBRead,
):
    uc = KBUseCases(db=db)
    added = await uc.toggle_favorite(article_id=article_id, user_id=current_user.user_id)
    return SuccessResponse.ok({"favorited": added})


@router.get("/favorites", response_model=SuccessResponse[list[dict]])
async def get_my_favorites(
    db: DBSession,
    current_user: CurrentUser = KBRead,
):
    uc = KBUseCases(db=db)
    articles = await uc.get_favorites(user_id=current_user.user_id)
    return SuccessResponse.ok([_serialize_article(a) for a in articles])


# ── Document Types ────────────────────────────────────────────────────────────

def _serialize_document_type(dt) -> dict:
    return {
        "id": dt.id,
        "code": dt.code,
        "name": dt.name,
        "icon": dt.icon,
        "color": dt.color,
        "is_active": dt.is_active,
        "sort_order": dt.sort_order,
    }


@router.get("/document-types", response_model=SuccessResponse[list[dict]])
async def list_document_types(
    db: DBSession,
    include_inactive: bool = Query(default=False),
    current_user: CurrentUser = DocTypeRead,
):
    uc = KBUseCases(db=db)
    types = await uc.list_document_types(include_inactive=include_inactive)
    return SuccessResponse.ok([_serialize_document_type(t) for t in types])


@router.post("/document-types", status_code=201)
async def create_document_type(
    body: DocumentTypeCreateDTO,
    db: DBSession,
    current_user: CurrentUser = DocTypeCreate,
):
    uc = KBUseCases(db=db)
    dt = await uc.create_document_type(
        code=body.code,
        name=body.name,
        icon=body.icon,
        color=body.color,
        sort_order=body.sort_order,
    )
    return SuccessResponse.ok(_serialize_document_type(dt))


@router.patch("/document-types/{document_type_id}")
async def update_document_type(
    document_type_id: str,
    body: DocumentTypeUpdateDTO,
    db: DBSession,
    current_user: CurrentUser = DocTypeUpdate,
):
    uc = KBUseCases(db=db)
    dt = await uc.update_document_type(
        document_type_id=document_type_id,
        name=body.name,
        icon=body.icon,
        color=body.color,
        sort_order=body.sort_order,
        is_active=body.is_active,
    )
    return SuccessResponse.ok(_serialize_document_type(dt))


@router.delete("/document-types/{document_type_id}", status_code=204)
async def delete_document_type(
    document_type_id: str,
    db: DBSession,
    current_user: CurrentUser = DocTypeDelete,
):
    uc = KBUseCases(db=db)
    await uc.delete_document_type(document_type_id=document_type_id)
    return None


def _serialize_article(a) -> dict:
    doc_type = None
    if a.document_type_id is not None and getattr(a, "document_type", None):
        doc_type = {
            "id": a.document_type.id,
            "code": a.document_type.code,
            "name": a.document_type.name,
            "icon": a.document_type.icon,
            "color": a.document_type.color,
        }
    return {
        "id": a.id,
        "title": a.title,
        "content_json": a.content_json,
        "content_text": a.content_text,
        "status": a.status,
        "version": a.version,
        "created_by_id": a.created_by_id,
        "approved_by_id": a.approved_by_id,
        "published_at": a.published_at.isoformat() if a.published_at else None,
        "view_count": a.view_count,
        "helpful_count": a.helpful_count,
        "not_helpful_count": a.not_helpful_count,
        "created_at": a.created_at.isoformat(),
        "updated_at": a.updated_at.isoformat(),
        "document_type_id": a.document_type_id,
        "document_type": doc_type,
    }
