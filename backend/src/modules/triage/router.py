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

from backend.src.modules.triage.application.catalog_use_cases import (
    TriageCatalogUseCases,
)
from backend.src.modules.triage.application.dtos import (
    CaseTriageResponse,
    CreateSlaPolicyPayload,
    CreateToolActionPayload,
    CreateToolTypePayload,
    CreateTriagePayload,
    TriageSlaPolicyResponse,
    TriageToolActionResponse,
    TriageToolTypeResponse,
    TriageWithContext,
    UpdateSlaPolicyPayload,
    UpdateToolActionPayload,
    UpdateToolTypePayload,
)
from backend.src.modules.triage.application.use_cases import TriageUseCases


router = APIRouter(prefix="/api/v1/cases", tags=["triage"])
# Separate router for read-only catalog endpoints (different URL prefix).
catalogs_router = APIRouter(prefix="/api/v1/triage-catalogs", tags=["triage"])

_Read = Depends(PermissionChecker("cases", "read"))
_Update = Depends(PermissionChecker("cases", "update"))
# Catalog admin reuses the taxonomy global-management permission --
# same SOC-admin persona, avoids seeding a new permission + role grant.
_ManageCatalogs = Depends(PermissionChecker("security_taxonomies", "manage_global"))


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


# ── Catalogs (separate router with /api/v1/triage-catalogs) ─────────
#
# Reads gated by cases:read (anyone triaging needs the dropdowns).
# Writes gated by security_taxonomies:manage_global (SOC admin).
# `include_inactive` query param lets the admin UI show disabled rows.


# ----- Tool types -----

@catalogs_router.get(
    "/tool-types",
    response_model=SuccessResponse[list[TriageToolTypeResponse]],
)
async def list_tool_types(
    db: DBSession,
    include_inactive: bool = False,
    _current_user: CurrentUser = _Read,
):
    rows = await TriageCatalogUseCases(db).list_tool_types(
        include_inactive=include_inactive,
    )
    return SuccessResponse.ok(rows)


@catalogs_router.post(
    "/tool-types",
    response_model=SuccessResponse[TriageToolTypeResponse],
    status_code=201,
)
async def create_tool_type(
    payload: CreateToolTypePayload,
    db: DBSession,
    _current_user: CurrentUser = _ManageCatalogs,
):
    row = await TriageCatalogUseCases(db).create_tool_type(payload)
    await db.commit()
    await db.refresh(row)
    return SuccessResponse.ok(row)


@catalogs_router.put(
    "/tool-types/{tool_type_id}",
    response_model=SuccessResponse[TriageToolTypeResponse],
)
async def update_tool_type(
    tool_type_id: str,
    payload: UpdateToolTypePayload,
    db: DBSession,
    _current_user: CurrentUser = _ManageCatalogs,
):
    row = await TriageCatalogUseCases(db).update_tool_type(tool_type_id, payload)
    await db.commit()
    await db.refresh(row)
    return SuccessResponse.ok(row)


@catalogs_router.delete("/tool-types/{tool_type_id}", status_code=204)
async def delete_tool_type(
    tool_type_id: str,
    db: DBSession,
    _current_user: CurrentUser = _ManageCatalogs,
):
    await TriageCatalogUseCases(db).delete_tool_type(tool_type_id)
    await db.commit()


# ----- Tool actions -----

@catalogs_router.get(
    "/tool-actions",
    response_model=SuccessResponse[list[TriageToolActionResponse]],
)
async def list_tool_actions(
    db: DBSession,
    include_inactive: bool = False,
    _current_user: CurrentUser = _Read,
):
    rows = await TriageCatalogUseCases(db).list_tool_actions(
        include_inactive=include_inactive,
    )
    return SuccessResponse.ok(rows)


@catalogs_router.post(
    "/tool-actions",
    response_model=SuccessResponse[TriageToolActionResponse],
    status_code=201,
)
async def create_tool_action(
    payload: CreateToolActionPayload,
    db: DBSession,
    _current_user: CurrentUser = _ManageCatalogs,
):
    row = await TriageCatalogUseCases(db).create_tool_action(payload)
    await db.commit()
    await db.refresh(row)
    return SuccessResponse.ok(row)


@catalogs_router.put(
    "/tool-actions/{action_id}",
    response_model=SuccessResponse[TriageToolActionResponse],
)
async def update_tool_action(
    action_id: str,
    payload: UpdateToolActionPayload,
    db: DBSession,
    _current_user: CurrentUser = _ManageCatalogs,
):
    row = await TriageCatalogUseCases(db).update_tool_action(action_id, payload)
    await db.commit()
    await db.refresh(row)
    return SuccessResponse.ok(row)


@catalogs_router.delete("/tool-actions/{action_id}", status_code=204)
async def delete_tool_action(
    action_id: str,
    db: DBSession,
    _current_user: CurrentUser = _ManageCatalogs,
):
    await TriageCatalogUseCases(db).delete_tool_action(action_id)
    await db.commit()


# ----- SLA policies -----

@catalogs_router.get(
    "/sla-policies",
    response_model=SuccessResponse[list[TriageSlaPolicyResponse]],
)
async def list_sla_policies(
    db: DBSession,
    _current_user: CurrentUser = _Read,
):
    rows = await TriageCatalogUseCases(db).list_sla_policies()
    return SuccessResponse.ok(rows)


@catalogs_router.post(
    "/sla-policies",
    response_model=SuccessResponse[TriageSlaPolicyResponse],
    status_code=201,
)
async def create_sla_policy(
    payload: CreateSlaPolicyPayload,
    db: DBSession,
    _current_user: CurrentUser = _ManageCatalogs,
):
    row = await TriageCatalogUseCases(db).create_sla_policy(payload)
    await db.commit()
    await db.refresh(row)
    return SuccessResponse.ok(row)


@catalogs_router.put(
    "/sla-policies/{policy_id}",
    response_model=SuccessResponse[TriageSlaPolicyResponse],
)
async def update_sla_policy(
    policy_id: str,
    payload: UpdateSlaPolicyPayload,
    db: DBSession,
    _current_user: CurrentUser = _ManageCatalogs,
):
    row = await TriageCatalogUseCases(db).update_sla_policy(policy_id, payload)
    await db.commit()
    await db.refresh(row)
    return SuccessResponse.ok(row)


@catalogs_router.delete("/sla-policies/{policy_id}", status_code=204)
async def delete_sla_policy(
    policy_id: str,
    db: DBSession,
    _current_user: CurrentUser = _ManageCatalogs,
):
    await TriageCatalogUseCases(db).delete_sla_policy(policy_id)
    await db.commit()
