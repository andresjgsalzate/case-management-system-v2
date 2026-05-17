"""HTTP router for the operational_center module (Sub-spec 06).

Endpoints (JWT + module-specific permission gates):
- GET  /api/v1/operational/dashboard/summary
- GET  /api/v1/operational/dashboard/stream      (text/event-stream)
- GET  /api/v1/operational/integration-health    (latest snapshot per source)
- GET  /api/v1/operational/integration-health/{source_id}/history
- GET  /api/v1/operational/approval-requests/inbox
- POST /api/v1/operational/audit-explorer/query
- POST /api/v1/operational/audit-explorer/export (CSV download)
"""
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import PlainTextResponse, StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

from backend.src.core.dependencies import DBSession
from backend.src.core.middleware.permission_checker import (
    CurrentUser,
    PermissionChecker,
)
from backend.src.core.responses import SuccessResponse
from backend.src.modules.operational_center.application.audit_explorer import (
    AuditFilters,
    export_audit_events_csv,
    query_audit_events,
)
from backend.src.modules.operational_center.application.dtos import (
    AuditEventDTO,
    AuditQueryResult,
    DashboardSummaryDTO,
)
from backend.src.modules.operational_center.application.sse_stream import (
    stream_dashboard_events,
)
from backend.src.modules.operational_center.application.use_cases import (
    OperationalCenterUseCases,
)


router = APIRouter(prefix="/api/v1/operational", tags=["operational-center"])

DashboardReadDep = Depends(PermissionChecker("dashboard_soc", "read"))
HealthReadDep = Depends(PermissionChecker("integration_health", "read"))
AuditReadDep = Depends(PermissionChecker("audit_explorer", "read"))
AuditExportDep = Depends(PermissionChecker("audit_explorer", "export"))
ApprovalsReadDep = Depends(PermissionChecker("approvals", "read"))


# ── Dashboard ─────────────────────────────────────────────────────────


@router.get(
    "/dashboard/summary",
    response_model=SuccessResponse[DashboardSummaryDTO],
)
async def get_dashboard_summary(
    db: DBSession,
    period_hours: int = Query(default=24, ge=1, le=168),
    current_user: CurrentUser = DashboardReadDep,
):
    uc = OperationalCenterUseCases(db=db)
    summary = await uc.get_dashboard_summary(
        actor=current_user, period_hours=period_hours,
    )
    return SuccessResponse.ok(summary)


@router.get("/dashboard/stream")
async def dashboard_stream(
    current_user: CurrentUser = DashboardReadDep,
):
    """SSE stream of dashboard events for `current_user.tenant_id`.

    Frontend's EventSource subscribes here; backend yields `connected` then
    streams events from the per-tenant subscriber queue + heartbeats.
    """
    return StreamingResponse(
        stream_dashboard_events(tenant_id=current_user.tenant_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # disable nginx buffering
        },
    )


# ── Integration health ────────────────────────────────────────────────


@router.get(
    "/integration-health",
    response_model=SuccessResponse[list[dict]],
)
async def list_integration_health(
    db: DBSession,
    current_user: CurrentUser = HealthReadDep,
):
    """Latest snapshot per source for current tenant."""
    from backend.src.modules.operational_center.application.dashboard_summary import (
        integration_health_summary,
    )
    rows = await integration_health_summary(db, current_user.tenant_id)
    return SuccessResponse.ok(rows)


@router.get(
    "/integration-health/{source_id}/history",
    response_model=SuccessResponse[list[dict]],
)
async def get_integration_health_history(
    source_id: str,
    db: DBSession,
    hours: int = Query(default=6, ge=1, le=720),
    current_user: CurrentUser = HealthReadDep,
):
    uc = OperationalCenterUseCases(db=db)
    rows = await uc.get_integration_health_detail(
        tenant_id=current_user.tenant_id, source_id=source_id, hours=hours,
    )
    return SuccessResponse.ok(rows)


# ── Approval inbox ────────────────────────────────────────────────────


@router.get(
    "/approval-requests/inbox",
    response_model=SuccessResponse[list[dict]],
)
async def list_approval_inbox(
    db: DBSession,
    status: str = Query(default="pending"),
    case_id: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    current_user: CurrentUser = ApprovalsReadDep,
):
    uc = OperationalCenterUseCases(db=db)
    rows = await uc.get_approval_inbox(
        actor=current_user, status=status, case_id=case_id,
        limit=limit, offset=offset,
    )
    return SuccessResponse.ok(rows)


# ── Audit Explorer ────────────────────────────────────────────────────


class AuditQueryPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: str | None = None
    date_from: datetime | None = None
    date_to: datetime | None = None
    sources: list[str] | None = None
    search: str | None = None
    limit: int = Field(default=200, ge=1, le=500)
    offset: int = Field(default=0, ge=0)


def _make_filters(payload: AuditQueryPayload, tenant_id: str) -> AuditFilters:
    return AuditFilters(
        tenant_id=tenant_id,
        case_id=payload.case_id,
        date_from=payload.date_from,
        date_to=payload.date_to,
        sources=payload.sources,
        search=payload.search,
        limit=payload.limit,
        offset=payload.offset,
    )


@router.post(
    "/audit-explorer/query",
    response_model=SuccessResponse[AuditQueryResult],
)
async def query_audit(
    payload: AuditQueryPayload,
    db: DBSession,
    current_user: CurrentUser = AuditReadDep,
):
    filters = _make_filters(payload, current_user.tenant_id)
    result = await query_audit_events(db, filters)
    return SuccessResponse.ok(AuditQueryResult(
        events=[AuditEventDTO(**e) for e in result["events"]],
        total=result["total"],
    ))


@router.post("/audit-explorer/export", response_class=PlainTextResponse)
async def export_audit(
    payload: AuditQueryPayload,
    db: DBSession,
    current_user: CurrentUser = AuditExportDep,
):
    """Returns CSV body with a Content-Disposition attachment header."""
    filters = _make_filters(payload, current_user.tenant_id)
    csv_str = await export_audit_events_csv(db, filters)
    return PlainTextResponse(
        content=csv_str,
        media_type="text/csv",
        headers={
            "Content-Disposition": "attachment; filename=audit-export.csv",
        },
    )
