"""HTTP router for the n8n_bridge module (Sub-spec 05).

Endpoints:
- Public callback (no JWT — uses HMAC + optional callback_jwt header):
    POST /api/v1/integrations/callbacks/n8n

- Admin / operator (JWT + n8n_bridge:* permission gates):
    GET  /api/v1/playbook-runs
    GET  /api/v1/playbook-runs/{id}
    GET  /api/v1/playbook-runs/{id}/callbacks
    POST /api/v1/cases/{case_id}/trigger-workflow

- Approvals (JWT + approvals:* permission gates):
    GET  /api/v1/approval-requests
    GET  /api/v1/approval-requests/{id}
    POST /api/v1/approval-requests/{id}/decide
"""
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import and_, or_, select

from backend.src.core.config import get_settings
from backend.src.core.dependencies import DBSession
from backend.src.core.exceptions import (
    BusinessRuleError,
    NotFoundError,
    UnauthorizedError,
    ValidationError,
)
from backend.src.core.middleware.permission_checker import (
    CurrentUser,
    PermissionChecker,
)
from backend.src.core.responses import SuccessResponse
from backend.src.modules.n8n_bridge.application.dtos import (
    ApprovalDecidePayload,
    ApprovalRequestResponse,
    CallbackPayload,
    ManualTriggerPayload,
    PlaybookRunCallbackResponse,
    PlaybookRunResponse,
)
from backend.src.modules.n8n_bridge.application.use_cases import (
    N8nBridgeUseCases,
)
from backend.src.modules.n8n_bridge.infrastructure.models import (
    ApprovalRequestModel,
    PlaybookRunCallbackModel,
    PlaybookRunModel,
)


# Two routers (public callbacks vs JWT-gated admin) — same pattern as Sub-spec 04.
webhook_router = APIRouter(
    prefix="/api/v1/integrations", tags=["n8n-bridge-callback"],
)
admin_router = APIRouter(prefix="/api/v1", tags=["n8n-bridge-admin"])

TriggerDep = Depends(PermissionChecker("n8n_bridge", "trigger_workflow"))
ReadRunsDep = Depends(PermissionChecker("n8n_bridge", "read_runs"))
ApprovalsReadDep = Depends(PermissionChecker("approvals", "read"))
ApprovalsApproveDep = Depends(PermissionChecker("approvals", "approve"))


# ── Public callback ────────────────────────────────────────────────────


@webhook_router.post(
    "/callbacks/n8n",
    response_model=SuccessResponse[dict],
)
async def n8n_callback(
    request: Request,
    db: DBSession,
):
    """n8n posts here with `{action, playbook_run_id, payload}` body.

    Auth is HMAC (mandatory) + JWT (optional second factor), validated
    inside handle_callback. No JWT bearer for the operator — n8n is the caller.
    """
    body = await request.body()
    headers = {k.lower(): v for k, v in request.headers.items()}
    try:
        parsed = CallbackPayload.model_validate_json(body)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid callback body: {e}")

    settings = get_settings()
    uc = N8nBridgeUseCases(db=db, cms_base_url=settings.CMS_BASE_URL)
    try:
        result = await uc.handle_callback(
            action=parsed.action,
            payload=parsed.payload,
            playbook_run_id=parsed.playbook_run_id,
            request_body=body,
            request_headers=headers,
        )
    except UnauthorizedError as e:
        raise HTTPException(status_code=401, detail=str(e))
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return SuccessResponse.ok(result)


# ── Playbook runs ──────────────────────────────────────────────────────


@admin_router.get(
    "/playbook-runs",
    response_model=SuccessResponse[list[PlaybookRunResponse]],
)
async def list_playbook_runs(
    db: DBSession,
    case_id: str | None = Query(default=None),
    status: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    current_user: CurrentUser = ReadRunsDep,
):
    conditions = [PlaybookRunModel.tenant_id == current_user.tenant_id]
    if case_id:
        conditions.append(PlaybookRunModel.case_id == case_id)
    if status:
        conditions.append(PlaybookRunModel.status == status)
    stmt = (
        select(PlaybookRunModel)
        .where(and_(*conditions))
        .order_by(PlaybookRunModel.triggered_at.desc())
        .limit(limit)
    )
    rows = (await db.execute(stmt)).scalars().all()
    return SuccessResponse.ok(
        [PlaybookRunResponse.model_validate(r) for r in rows],
    )


@admin_router.get(
    "/playbook-runs/{run_id}",
    response_model=SuccessResponse[PlaybookRunResponse],
)
async def get_playbook_run(
    run_id: str,
    db: DBSession,
    current_user: CurrentUser = ReadRunsDep,
):
    run = await db.get(PlaybookRunModel, run_id)
    if run is None or run.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=404, detail="playbook_run not found")
    return SuccessResponse.ok(PlaybookRunResponse.model_validate(run))


@admin_router.get(
    "/playbook-runs/{run_id}/callbacks",
    response_model=SuccessResponse[list[PlaybookRunCallbackResponse]],
)
async def list_playbook_run_callbacks(
    run_id: str,
    db: DBSession,
    current_user: CurrentUser = ReadRunsDep,
):
    run = await db.get(PlaybookRunModel, run_id)
    if run is None or run.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=404, detail="playbook_run not found")
    stmt = (
        select(PlaybookRunCallbackModel)
        .where(PlaybookRunCallbackModel.playbook_run_id == run_id)
        .order_by(PlaybookRunCallbackModel.received_at.asc())
    )
    rows = (await db.execute(stmt)).scalars().all()
    return SuccessResponse.ok(
        [PlaybookRunCallbackResponse.model_validate(r) for r in rows],
    )


# ── Operator-triggered workflow ────────────────────────────────────────


@admin_router.post(
    "/cases/{case_id}/trigger-workflow",
    response_model=SuccessResponse[PlaybookRunResponse],
    status_code=201,
)
async def trigger_workflow(
    case_id: str,
    payload: ManualTriggerPayload,
    db: DBSession,
    current_user: CurrentUser = TriggerDep,
):
    settings = get_settings()
    uc = N8nBridgeUseCases(
        db=db, cms_base_url=settings.CMS_BASE_URL,
        system_user_id=current_user.user_id,
    )
    try:
        run = await uc.trigger_workflow(
            case_id=case_id, workflow_url=payload.workflow_url,
            triggered_by="manual",
            triggered_by_user=current_user.user_id,
            extra_context=payload.extra_context,
        )
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except BusinessRuleError as e:
        # n8n unreachable or no n8n source configured for tenant
        raise HTTPException(status_code=502, detail=str(e))
    return SuccessResponse.ok(PlaybookRunResponse.model_validate(run))


# ── Approval inbox ─────────────────────────────────────────────────────


@admin_router.get(
    "/approval-requests",
    response_model=SuccessResponse[list[ApprovalRequestResponse]],
)
async def list_approval_requests(
    db: DBSession,
    status: str | None = Query(default=None),
    case_id: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    current_user: CurrentUser = ApprovalsReadDep,
):
    conditions = [ApprovalRequestModel.tenant_id == current_user.tenant_id]
    if status:
        conditions.append(ApprovalRequestModel.status == status)
    if case_id:
        conditions.append(ApprovalRequestModel.case_id == case_id)
    stmt = (
        select(ApprovalRequestModel)
        .where(and_(*conditions))
        .order_by(ApprovalRequestModel.created_at.desc())
        .limit(limit)
    )
    rows = (await db.execute(stmt)).scalars().all()
    return SuccessResponse.ok(
        [ApprovalRequestResponse.model_validate(r) for r in rows],
    )


@admin_router.get(
    "/approval-requests/{approval_id}",
    response_model=SuccessResponse[ApprovalRequestResponse],
)
async def get_approval_request(
    approval_id: str,
    db: DBSession,
    current_user: CurrentUser = ApprovalsReadDep,
):
    appr = await db.get(ApprovalRequestModel, approval_id)
    if appr is None or appr.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=404, detail="approval_request not found")
    return SuccessResponse.ok(ApprovalRequestResponse.model_validate(appr))


@admin_router.post(
    "/approval-requests/{approval_id}/decide",
    response_model=SuccessResponse[dict],
)
async def decide_approval(
    approval_id: str,
    payload: ApprovalDecidePayload,
    db: DBSession,
    current_user: CurrentUser = ApprovalsApproveDep,
):
    settings = get_settings()
    uc = N8nBridgeUseCases(db=db, cms_base_url=settings.CMS_BASE_URL)
    try:
        result = await uc.approve_or_reject(
            approval_id=approval_id,
            decision=payload.decision,
            approver_user_id=current_user.user_id,
            approver_name=getattr(current_user, "email", None),
            reason=payload.reason,
        )
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except BusinessRuleError as e:
        # Decision persisted but resume POST failed — surface as 502
        raise HTTPException(status_code=502, detail=str(e))
    return SuccessResponse.ok(result)
