"""MITRE ATT&CK lookup endpoint -- powers the taxonomy editor's picker."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from backend.src.core.middleware.permission_checker import (
    CurrentUser,
    PermissionChecker,
)
from backend.src.core.responses import SuccessResponse
from backend.src.modules.mitre import loader


router = APIRouter(prefix="/mitre", tags=["mitre"])


# The picker is used by the taxonomy editor (create + update flows).
# `security_taxonomies:read` is the least-privilege gate that still
# matches the audience -- anyone viewing taxonomies can audit which
# MITRE TTPs they map to, and editors need it for the picker.
_taxonomy_gate = PermissionChecker("security_taxonomies", "read")


@router.get("/techniques", response_model=SuccessResponse[list])
async def search_techniques(
    q: str = Query("", description="ID or name substring"),
    limit: int = Query(50, ge=1, le=200),
    _current_user: CurrentUser = Depends(_taxonomy_gate),
):
    return SuccessResponse.ok(await loader.search(q, limit=limit))


@router.get("/techniques/{technique_id}", response_model=SuccessResponse[dict])
async def get_technique(
    technique_id: str,
    _current_user: CurrentUser = Depends(_taxonomy_gate),
):
    t = await loader.get_by_id(technique_id)
    if not t:
        raise HTTPException(status_code=404, detail="Technique not found")
    return SuccessResponse.ok(t)


@router.post("/refresh", response_model=SuccessResponse[dict])
async def force_refresh(
    # Manual cache invalidation gated by the taxonomy admin permission.
    # Any user who can manage global taxonomies can force a refetch from
    # MITRE before the 24 h TTL elapses (e.g. "MITRE just published v15,
    # update the picker now").
    _current_user: CurrentUser = Depends(
        PermissionChecker("security_taxonomies", "manage_global"),
    ),
):
    data = await loader.get_all(force_refresh=True)
    return SuccessResponse.ok(
        {"count": len(data), "ttl_seconds": loader.CACHE_TTL_SECONDS}
    )
