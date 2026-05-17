"""Forensic module HTTP router.

Endpoint surface (mounted at ``/api/v1/forensic``):

| Method | Path                                    | Permission         |
|--------|-----------------------------------------|--------------------|
| GET    | /artifacts                              | forensic.read      |
| POST   | /artifacts/sync                         | forensic.sync_catalog |
| PATCH  | /artifacts/{artifact_id}                | forensic.manage_featured |
| GET    | /clients                                | forensic.read      |
| POST   | /cases/{case_id}/hunts                  | forensic.launch_ro |
| GET    | /hunts                                  | forensic.read      |
| GET    | /hunts/{hunt_id}                        | forensic.read      |
| POST   | /hunts/{hunt_id}/cancel                 | forensic.cancel_own |
| GET    | /hunts/{hunt_id}/results                | forensic.read      |

Destructive launches do NOT have a UI endpoint — they only reach
``ForensicUseCases.launch_hunt`` through the n8n bridge's
``attach_artifact`` flow (Task 11), gated by ``_enforce_destructive_governance``.
"""
from typing import Any

from fastapi import APIRouter, Depends, Query, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from backend.src.core.dependencies import DBSession
from backend.src.core.middleware.permission_checker import (
    CurrentUser, PermissionChecker,
)
from backend.src.core.responses import SuccessResponse
from backend.src.modules.forensic.application.dtos import LaunchHuntDTO
from backend.src.modules.forensic.application.use_cases import ForensicUseCases
from backend.src.modules.forensic.infrastructure.models import (
    ForensicArtifactModel, ForensicHuntModel, ForensicHuntResultModel,
)


router = APIRouter(prefix="/api/v1/forensic", tags=["forensic"])

ForensicRead = Depends(PermissionChecker("forensic", "read"))
ForensicLaunchRO = Depends(PermissionChecker("forensic", "launch_ro"))
ForensicCancelOwn = Depends(PermissionChecker("forensic", "cancel_own"))
ForensicSyncCatalog = Depends(PermissionChecker("forensic", "sync_catalog"))
ForensicManageFeatured = Depends(
    PermissionChecker("forensic", "manage_featured")
)


# ── Catalog ───────────────────────────────────────────────────────────────

@router.get("/artifacts", response_model=SuccessResponse[list[dict]])
async def list_artifacts(
    db: DBSession,
    featured_only: bool = Query(default=False),
    category: str | None = Query(default=None),
    os: str | None = Query(default=None),
    search: str | None = Query(default=None),
    include_destructive: bool = Query(default=False),
    current_user: CurrentUser = ForensicRead,
):
    uc = ForensicUseCases(db=db)
    artifacts = await uc.list_artifacts(
        tenant_id=current_user.tenant_id,
        featured_only=featured_only,
        category=category,
        os=os,
        search=search,
        include_destructive=include_destructive,
    )
    return SuccessResponse.ok([_serialize_artifact(a) for a in artifacts])


@router.post("/artifacts/sync", response_model=SuccessResponse[dict])
async def sync_artifacts(
    db: DBSession,
    current_user: CurrentUser = ForensicSyncCatalog,
):
    from backend.src.modules.forensic.application.catalog_sync import (
        sync_all_tenants,
    )
    await sync_all_tenants()
    return SuccessResponse.ok({"synced": True})


class PatchArtifactDTO(BaseModel):
    is_featured: bool | None = None
    is_destructive: bool | None = None
    requires_evidence_handling: bool | None = None
    category: str | None = None
    default_timeout_seconds: int | None = None


@router.patch("/artifacts/{artifact_id}", response_model=SuccessResponse[dict])
async def patch_artifact(
    artifact_id: str,
    body: PatchArtifactDTO,
    db: DBSession,
    current_user: CurrentUser = ForensicManageFeatured,
):
    artifact = await db.get(ForensicArtifactModel, artifact_id)
    if not artifact:
        raise HTTPException(status_code=404, detail="Artifact not found")
    for field in (
        "is_featured", "is_destructive", "requires_evidence_handling",
        "category", "default_timeout_seconds",
    ):
        val = getattr(body, field)
        if val is not None:
            setattr(artifact, field, val)
    await db.commit()
    return SuccessResponse.ok(_serialize_artifact(artifact))


# ── Clients ───────────────────────────────────────────────────────────────

@router.get("/clients", response_model=SuccessResponse[list[dict]])
async def list_clients(
    db: DBSession,
    search: str | None = Query(default=None),
    limit: int = Query(default=100, le=1000),
    current_user: CurrentUser = ForensicRead,
):
    uc = ForensicUseCases(db=db)
    clients = await uc.list_clients(
        tenant_id=current_user.tenant_id, search=search, limit=limit
    )
    return SuccessResponse.ok([c.model_dump() for c in clients])


# ── Hunts ─────────────────────────────────────────────────────────────────

@router.post(
    "/cases/{case_id}/hunts",
    response_model=SuccessResponse[dict],
    status_code=201,
)
async def launch_hunt_for_case(
    case_id: str,
    body: LaunchHuntDTO,
    db: DBSession,
    current_user: CurrentUser = ForensicLaunchRO,
):
    uc = ForensicUseCases(db=db)
    hunt = await uc.launch_hunt(
        actor=current_user,
        case_id=case_id,
        artifact_id=body.artifact_id,
        parameters=body.parameters,
        target_clients=body.target_clients,
        timeout_seconds=body.timeout_seconds,
    )
    return SuccessResponse.ok(_serialize_hunt(hunt))


@router.get("/hunts", response_model=SuccessResponse[list[dict]])
async def list_hunts(
    db: DBSession,
    case_id: str | None = Query(default=None),
    status: str | None = Query(default=None),
    limit: int = Query(default=50, le=200),
    current_user: CurrentUser = ForensicRead,
):
    stmt = select(ForensicHuntModel).where(
        ForensicHuntModel.tenant_id == current_user.tenant_id
    )
    if case_id:
        stmt = stmt.where(ForensicHuntModel.case_id == case_id)
    if status:
        stmt = stmt.where(ForensicHuntModel.status == status)
    stmt = stmt.order_by(ForensicHuntModel.started_at.desc()).limit(limit)
    result = await db.execute(stmt)
    hunts = result.scalars().all()
    return SuccessResponse.ok([_serialize_hunt(h) for h in hunts])


@router.get("/hunts/{hunt_id}", response_model=SuccessResponse[dict])
async def get_hunt(
    hunt_id: str,
    db: DBSession,
    current_user: CurrentUser = ForensicRead,
):
    hunt = await db.get(ForensicHuntModel, hunt_id)
    if not hunt or hunt.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=404, detail="Hunt not found")
    return SuccessResponse.ok(_serialize_hunt(hunt, include_chain=True))


class CancelHuntDTO(BaseModel):
    reason: str | None = None


@router.post(
    "/hunts/{hunt_id}/cancel", response_model=SuccessResponse[dict],
)
async def cancel_hunt(
    hunt_id: str,
    body: CancelHuntDTO,
    db: DBSession,
    current_user: CurrentUser = ForensicCancelOwn,
):
    uc = ForensicUseCases(db=db)
    hunt = await uc.cancel_hunt(
        actor=current_user, hunt_id=hunt_id, reason=body.reason
    )
    return SuccessResponse.ok(_serialize_hunt(hunt))


@router.get(
    "/hunts/{hunt_id}/results", response_model=SuccessResponse[list[dict]],
)
async def list_hunt_results(
    hunt_id: str,
    db: DBSession,
    limit: int = Query(default=50, le=500),
    offset: int = Query(default=0),
    current_user: CurrentUser = ForensicRead,
):
    hunt = await db.get(ForensicHuntModel, hunt_id)
    if not hunt or hunt.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=404, detail="Hunt not found")
    stmt = (
        select(ForensicHuntResultModel)
        .where(ForensicHuntResultModel.hunt_id == hunt_id)
        .order_by(ForensicHuntResultModel.collected_at.desc())
        .limit(limit).offset(offset)
    )
    rows = (await db.execute(stmt)).scalars().all()
    return SuccessResponse.ok([_serialize_result(r) for r in rows])


# ── Serializers ───────────────────────────────────────────────────────────

def _serialize_artifact(a: ForensicArtifactModel) -> dict[str, Any]:
    return {
        "id": a.id,
        "name": a.name,
        "description": a.description,
        "artifact_type": a.artifact_type,
        "supported_os": a.supported_os,
        "parameters_schema": a.parameters_schema,
        "is_featured": a.is_featured,
        "is_destructive": a.is_destructive,
        "requires_evidence_handling": a.requires_evidence_handling,
        "default_timeout_seconds": a.default_timeout_seconds,
        "category": a.category,
        "is_active": a.is_active,
        "last_synced_at": a.last_synced_at.isoformat(),
    }


def _serialize_hunt(
    h: ForensicHuntModel, include_chain: bool = False
) -> dict[str, Any]:
    out: dict[str, Any] = {
        "id": h.id,
        "case_id": h.case_id,
        "artifact_id": h.artifact_id,
        "artifact_name": h.artifact_name,
        "target_label": h.target_label,
        "status": h.status,
        "started_at": h.started_at.isoformat(),
        "completed_at": (
            h.completed_at.isoformat() if h.completed_at else None
        ),
        "timeout_at": h.timeout_at.isoformat(),
        "launched_via": h.launched_via,
        "launched_by_user_id": h.launched_by_user_id,
        "result_summary": h.result_summary,
        "error": h.error,
    }
    if include_chain:
        out["chain_of_custody"] = {
            "result_hash": h.result_hash,
            "velo_hunt_id": h.velo_hunt_id,
            "velo_org_id": h.velo_org_id,
            "approval_request_id": h.approval_request_id,
        }
    return out


def _serialize_result(r: ForensicHuntResultModel) -> dict[str, Any]:
    return {
        "id": r.id,
        "velo_client_id": r.velo_client_id,
        "hostname": r.hostname,
        "os": r.os,
        "output_summary": r.output_summary,
        "output_total_rows": r.output_total_rows,
        "attachments_count": r.attachments_count,
        "status": r.status,
        "row_hash": r.row_hash,
        "collected_at": r.collected_at.isoformat(),
    }
