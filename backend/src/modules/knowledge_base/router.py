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


class TagCreateDTO(BaseModel):
    name: str
    slug: str


class ArticleCreateDTO(BaseModel):
    title: str
    content_json: dict[str, Any]
    content_text: str
    tag_ids: list[str] = []


class ArticleUpdateDTO(BaseModel):
    title: str | None = None
    content_json: dict[str, Any] | None = None
    content_text: str | None = None
    tag_ids: list[str] | None = None


class TransitionDTO(BaseModel):
    to_status: str
    comment: str | None = None


class FeedbackDTO(BaseModel):
    is_helpful: bool
    comment: str | None = None


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
    limit: int = Query(default=20, le=100),
    offset: int = Query(default=0),
    current_user: CurrentUser = KBRead,
):
    uc = KBUseCases(db=db)
    articles = await uc.list_articles(
        status=status,
        tenant_id=current_user.tenant_id,
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
    )
    return SuccessResponse.ok(_serialize_article(article))


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
    )
    return SuccessResponse.ok(_serialize_article(article))


@router.post("/articles/{article_id}/transitions")
async def transition_article(
    article_id: str,
    body: TransitionDTO,
    db: DBSession,
    current_user: CurrentUser = KBCreate,
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


def _serialize_article(a) -> dict:
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
    }
