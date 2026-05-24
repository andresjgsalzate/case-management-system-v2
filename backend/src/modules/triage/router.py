"""HTTP router for the SOC triage module (Phase 2 of docs/specs/triage.md).

Endpoints:

  GET    /api/v1/cases/{case_id}/triage              -> current (latest version)
  GET    /api/v1/cases/{case_id}/triage/history      -> every revision
  POST   /api/v1/cases/{case_id}/triage              -> create new revision

Permissions:
  - Read endpoints gated by `cases:read` (anyone who can see the case
    can see its triage).
  - Create endpoint gated by `cases:update` (analyst-level capability).
  Triage doesn't have a dedicated permission yet; can split later if
  we want a "triage:create" role.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from backend.src.core.dependencies import DBSession
from backend.src.core.middleware.permission_checker import (
    CurrentUser,
    PermissionChecker,
)
from backend.src.core.responses import SuccessResponse
from sqlalchemy import select

from backend.src.modules.triage.application.dtos import (
    CaseTriageResponse,
    CreateTriagePayload,
    TriageToolActionResponse,
    TriageToolTypeResponse,
    TriageWithContext,
)
from backend.src.modules.triage.application.use_cases import TriageUseCases
from backend.src.modules.triage.infrastructure.models import (
    TriageToolActionModel,
    TriageToolTypeModel,
)


router = APIRouter(prefix="/api/v1/cases", tags=["triage"])
# Separate router for read-only catalog endpoints (different URL prefix).
catalogs_router = APIRouter(prefix="/api/v1/triage-catalogs", tags=["triage"])

_Read = Depends(PermissionChecker("cases", "read"))
_Update = Depends(PermissionChecker("cases", "update"))


@router.get(
    "/{case_id}/triage",
    response_model=SuccessResponse[TriageWithContext | None],
)
async def get_current_triage(
    case_id: str,
    db: DBSession,
    _current_user: CurrentUser = _Read,
):
    """Latest triage revision plus auto-derived context (parent taxonomy,
    sub name, resolved impact). Returns null when the case has never been
    triaged.
    """
    uc = TriageUseCases(db)
    triage = await uc.get_current(case_id)
    if triage is None:
        return SuccessResponse.ok(None)
    enriched = await uc.enrich_with_context(triage)
    return SuccessResponse.ok(TriageWithContext.model_validate(enriched))


@router.get(
    "/{case_id}/triage/history",
    response_model=SuccessResponse[list[CaseTriageResponse]],
)
async def list_triage_history(
    case_id: str,
    db: DBSession,
    _current_user: CurrentUser = _Read,
):
    """Every triage revision for the case, newest first."""
    uc = TriageUseCases(db)
    rows = await uc.list_history(case_id)
    return SuccessResponse.ok(rows)


@router.post(
    "/{case_id}/triage",
    response_model=SuccessResponse[CaseTriageResponse],
    status_code=201,
)
async def create_triage(
    case_id: str,
    payload: CreateTriagePayload,
    db: DBSession,
    current_user: CurrentUser = _Update,
):
    """Create a new triage revision. Updates case.priority_id with the
    calculated priority (when one is resolved). Each call creates a new
    versioned row; "update" semantics are achieved by creating another
    revision (history-preserving design).
    """
    uc = TriageUseCases(db)
    triage = await uc.create_triage(
        case_id=case_id,
        actor_user_id=current_user.user_id,
        payload=payload,
    )
    await db.commit()
    await db.refresh(triage)
    return SuccessResponse.ok(triage)


# ── Catalogs (read-only, separate router with /api/v1/triage-catalogs) ──


@catalogs_router.get(
    "/tool-types",
    response_model=SuccessResponse[list[TriageToolTypeResponse]],
)
async def list_tool_types(
    db: DBSession,
    _current_user: CurrentUser = _Read,
):
    """All active tool types (xlsx Herramientas). Tenant scoping ignored
    for now -- catalog is global until /settings UI lands in Phase 5.
    """
    stmt = (
        select(TriageToolTypeModel)
        .where(TriageToolTypeModel.is_active.is_(True))
        .order_by(TriageToolTypeModel.name)
    )
    rows = (await db.execute(stmt)).scalars().all()
    return SuccessResponse.ok(rows)


@catalogs_router.get(
    "/tool-actions",
    response_model=SuccessResponse[list[TriageToolActionResponse]],
)
async def list_tool_actions(
    db: DBSession,
    _current_user: CurrentUser = _Read,
):
    """All active tool actions (Monitoreo / Bloqueo / extensible)."""
    stmt = (
        select(TriageToolActionModel)
        .where(TriageToolActionModel.is_active.is_(True))
        .order_by(TriageToolActionModel.name)
    )
    rows = (await db.execute(stmt)).scalars().all()
    return SuccessResponse.ok(rows)
