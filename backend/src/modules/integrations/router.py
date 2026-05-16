"""HTTP router for the integrations module (Sub-spec 04).

Endpoints:
- Public webhook (no JWT — uses per-source HMAC/API key/bearer auth):
    POST /api/v1/integrations/sources/{source_id}/events

- Admin (JWT + integrations:* permission gates):
    GET   /api/v1/integration-sources
    POST  /api/v1/integration-sources                  → returns secret ONCE
    PATCH /api/v1/integration-sources/{id}
    POST  /api/v1/integration-sources/{id}/rotate-secret → returns secret ONCE
    DELETE /api/v1/integration-sources/{id}            → soft-delete (is_active=false)

- Operator (JWT + replay/read_events gates):
    GET  /api/v1/inbound-events
    GET  /api/v1/inbound-events/{id}
    POST /api/v1/inbound-events/{id}/replay
"""
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import and_, or_, select

from backend.src.core.dependencies import DBSession
from backend.src.core.exceptions import (
    ForbiddenError,
    NotFoundError,
    UnauthorizedError,
)
from backend.src.core.middleware.permission_checker import (
    CurrentUser,
    PermissionChecker,
)
from backend.src.core.responses import SuccessResponse
from backend.src.modules.integrations.application.dtos import (
    CreateSourcePayload,
    CreateSourceResponse,
    InboundEventResponse,
    ProcessEventResult,
    ReceiveEventResult,
    RotateSecretResponse,
    SourceResponse,
    UpdateSourcePayload,
)
from backend.src.modules.integrations.application.idempotency import (
    RateLimitExceededError,
)
from backend.src.modules.integrations.application.use_cases import (
    IntegrationsUseCases,
)
from backend.src.modules.integrations.infrastructure.models import (
    InboundEventModel,
)


# Two routers: public webhook lives under /integrations, admin endpoints
# directly under /api/v1/integration-sources etc. for cleaner URLs.
webhook_router = APIRouter(prefix="/api/v1/integrations", tags=["integrations-webhook"])
admin_router = APIRouter(prefix="/api/v1", tags=["integrations-admin"])

ReadDep = Depends(PermissionChecker("integrations", "read"))
ManageDep = Depends(PermissionChecker("integrations", "manage"))
ReadEventsDep = Depends(PermissionChecker("integrations", "read_events"))
ReplayEventsDep = Depends(PermissionChecker("integrations", "replay_events"))


# ── Public webhook (NO JWT) ────────────────────────────────────────────


@webhook_router.post(
    "/sources/{source_id}/events",
    response_model=SuccessResponse[ReceiveEventResult],
)
async def receive_event_webhook(
    source_id: str,
    request: Request,
    db: DBSession,
):
    """Webhook receiver. Auth is enforced per-source (HMAC/API key/bearer),
    not via JWT. Returns 200 on accept or duplicate; 4xx on failure."""
    body = await request.body()
    headers = dict(request.headers)
    uc = IntegrationsUseCases(db=db)
    try:
        result = await uc.receive_event(
            source_id=source_id,
            request_body=body,
            request_headers=headers,
        )
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ForbiddenError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except UnauthorizedError as e:
        raise HTTPException(status_code=401, detail=str(e))
    except RateLimitExceededError as e:
        raise HTTPException(status_code=429, detail=str(e))
    return SuccessResponse.ok(result)


# ── Source CRUD ────────────────────────────────────────────────────────


@admin_router.get(
    "/integration-sources",
    response_model=SuccessResponse[list[SourceResponse]],
)
async def list_sources(
    db: DBSession,
    current_user: CurrentUser = ReadDep,
):
    uc = IntegrationsUseCases(db=db)
    sources = await uc.list_sources(actor=current_user)
    return SuccessResponse.ok(sources)


@admin_router.post(
    "/integration-sources",
    response_model=SuccessResponse[CreateSourceResponse],
    status_code=201,
)
async def create_source(
    payload: CreateSourcePayload,
    request: Request,
    db: DBSession,
    current_user: CurrentUser = ManageDep,
):
    uc = IntegrationsUseCases(db=db)
    result = await uc.create_source(actor=current_user, payload=payload)
    # Fill the webhook_url so the operator can configure the upstream tool
    base = str(request.base_url).rstrip("/")
    result.webhook_url = (
        f"{base}/api/v1/integrations/sources/{result.source.id}/events"
    )
    return SuccessResponse.ok(result)


@admin_router.patch(
    "/integration-sources/{source_id}",
    response_model=SuccessResponse[SourceResponse],
)
async def update_source(
    source_id: str,
    payload: UpdateSourcePayload,
    db: DBSession,
    current_user: CurrentUser = ManageDep,
):
    uc = IntegrationsUseCases(db=db)
    updated = await uc.update_source(
        actor=current_user, source_id=source_id, payload=payload,
    )
    return SuccessResponse.ok(updated)


@admin_router.post(
    "/integration-sources/{source_id}/rotate-secret",
    response_model=SuccessResponse[RotateSecretResponse],
)
async def rotate_source_secret(
    source_id: str,
    db: DBSession,
    current_user: CurrentUser = ManageDep,
):
    uc = IntegrationsUseCases(db=db)
    return SuccessResponse.ok(
        await uc.rotate_secret(actor=current_user, source_id=source_id),
    )


@admin_router.delete(
    "/integration-sources/{source_id}",
    response_model=SuccessResponse[dict],
)
async def soft_delete_source(
    source_id: str,
    db: DBSession,
    current_user: CurrentUser = ManageDep,
):
    """Soft-delete by setting is_active=false (avoids FK violation with inbound_events)."""
    uc = IntegrationsUseCases(db=db)
    updated = await uc.update_source(
        actor=current_user, source_id=source_id,
        payload=UpdateSourcePayload(is_active=False),
    )
    return SuccessResponse.ok({"id": updated.id, "is_active": False})


# ── Inbound events log + replay ────────────────────────────────────────


@admin_router.get(
    "/inbound-events",
    response_model=SuccessResponse[list[InboundEventResponse]],
)
async def list_inbound_events(
    db: DBSession,
    status: str | None = Query(default=None),
    source_id: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    current_user: CurrentUser = ReadEventsDep,
):
    conditions = [
        or_(
            InboundEventModel.tenant_id == current_user.tenant_id,
            InboundEventModel.tenant_id.is_(None),
        ),
    ]
    if status:
        conditions.append(InboundEventModel.status == status)
    if source_id:
        conditions.append(InboundEventModel.source_id == source_id)
    stmt = (
        select(InboundEventModel)
        .where(and_(*conditions))
        .order_by(InboundEventModel.received_at.desc())
        .limit(limit)
    )
    rows = (await db.execute(stmt)).scalars().all()
    return SuccessResponse.ok(
        [InboundEventResponse.model_validate(r) for r in rows],
    )


@admin_router.get(
    "/inbound-events/{event_id}",
    response_model=SuccessResponse[InboundEventResponse],
)
async def get_inbound_event(
    event_id: str,
    db: DBSession,
    current_user: CurrentUser = ReadEventsDep,
):
    event = await db.get(InboundEventModel, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="inbound_event not found")
    return SuccessResponse.ok(InboundEventResponse.model_validate(event))


@admin_router.post(
    "/inbound-events/{event_id}/replay",
    response_model=SuccessResponse[ProcessEventResult],
)
async def replay_inbound_event(
    event_id: str,
    db: DBSession,
    current_user: CurrentUser = ReplayEventsDep,
):
    """Force a failed event back through the pipeline (resets counters)."""
    uc = IntegrationsUseCases(
        db=db,
        taxonomies_uc=_lazy_taxonomies_uc(db),
        prioritization_uc=_lazy_prioritization_uc(db),
        cases_uc=_lazy_cases_uc(db),
    )
    return SuccessResponse.ok(
        await uc.manual_replay(actor=current_user, inbound_event_id=event_id),
    )


# ── Lazy factories for peer UCs (avoid hard imports at module top) ────


def _lazy_taxonomies_uc(db):
    from backend.src.modules.security_taxonomies.application.use_cases import (
        SecurityTaxonomyUseCases,
    )
    return SecurityTaxonomyUseCases(db=db)


def _lazy_prioritization_uc(db):
    from backend.src.modules.prioritization.application.use_cases import (
        PrioritizationUseCases,
    )
    return PrioritizationUseCases(db=db)


def _lazy_cases_uc(db):
    from backend.src.modules.cases.application.use_cases import CaseUseCases
    return CaseUseCases(db=db)
