"""Workflow Change Request HTTP endpoints (sub-spec 09 §3.9)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from backend.src.core.dependencies import DBSession
from backend.src.core.middleware.permission_checker import (
    CurrentUser,
    PermissionChecker,
)
from backend.src.core.responses import SuccessResponse
from backend.src.modules.workflow_change_requests.application.dtos import (
    CreateWCRDTO,
    ImplementDTO,
    UpdateStatusDTO,
    WCRResponseDTO,
)
from backend.src.modules.workflow_change_requests.application.use_cases import (
    WCRUseCases,
)


router = APIRouter(
    prefix="/workflow-change-requests",
    tags=["workflow-change-requests"],
)


@router.get("", response_model=SuccessResponse[list[WCRResponseDTO]])
async def list_wcrs(
    db: DBSession,
    status: str | None = None,
    requester_id: str | None = None,
    current_user: CurrentUser = Depends(
        PermissionChecker("workflow_change_requests", "read")
    ),
):
    # Super admins see everything; tenant-scoped users see their tenant only.
    tenant_filter = None if current_user.is_global else current_user.tenant_id
    rows = await WCRUseCases(db).list(
        status=status,
        requester_id=requester_id,
        tenant_id=tenant_filter,
    )
    return SuccessResponse.ok(rows)


@router.get("/{wcr_id}", response_model=SuccessResponse[WCRResponseDTO])
async def get_wcr(
    wcr_id: str,
    db: DBSession,
    current_user: CurrentUser = Depends(
        PermissionChecker("workflow_change_requests", "read")
    ),
):
    # NotFoundError raised by the use case becomes a 404 via the global
    # AppError handler registered in main.py — no try/except needed here.
    wcr = await WCRUseCases(db).get(wcr_id)

    # Don't leak cross-tenant rows. Surface as 404 to avoid disclosing
    # the existence of rows the caller can't see.
    if (
        not current_user.is_global
        and wcr.tenant_id
        and wcr.tenant_id != current_user.tenant_id
    ):
        raise HTTPException(status_code=404, detail="WCR not found")
    return SuccessResponse.ok(wcr)


@router.post("", response_model=SuccessResponse[WCRResponseDTO], status_code=201)
async def create_wcr(
    dto: CreateWCRDTO,
    db: DBSession,
    current_user: CurrentUser = Depends(
        PermissionChecker("workflow_change_requests", "create")
    ),
):
    # Force tenant_id to the caller's tenant so requesters can't file on
    # behalf of another tenant. Super-admins may set it explicitly.
    if not current_user.is_global:
        dto = dto.model_copy(update={"tenant_id": current_user.tenant_id})

    wcr = await WCRUseCases(db).create(
        dto=dto, requester_id=current_user.user_id
    )
    return SuccessResponse.ok(wcr)


@router.patch(
    "/{wcr_id}/status", response_model=SuccessResponse[WCRResponseDTO]
)
async def transition_wcr(
    wcr_id: str,
    dto: UpdateStatusDTO,
    db: DBSession,
    current_user: CurrentUser = Depends(
        PermissionChecker("workflow_change_requests", "review")
    ),
):
    # ValueError on illegal state transition → 400 via global handler.
    try:
        wcr = await WCRUseCases(db).transition(
            wcr_id=wcr_id, dto=dto, reviewer_id=current_user.user_id
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return SuccessResponse.ok(wcr)


@router.post(
    "/{wcr_id}/implement", response_model=SuccessResponse[WCRResponseDTO]
)
async def implement_wcr(
    wcr_id: str,
    dto: ImplementDTO,
    db: DBSession,
    current_user: CurrentUser = Depends(
        PermissionChecker("workflow_change_requests", "review")
    ),
):
    try:
        wcr = await WCRUseCases(db).implement(
            wcr_id=wcr_id, dto=dto, reviewer_id=current_user.user_id
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return SuccessResponse.ok(wcr)
