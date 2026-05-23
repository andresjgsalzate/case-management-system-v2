"""n8n inventory HTTP endpoints (sub-spec 09 follow-up)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from backend.src.core.config import get_settings
from backend.src.core.dependencies import DBSession
from backend.src.core.middleware.permission_checker import (
    CurrentUser,
    PermissionChecker,
)
from backend.src.core.responses import SuccessResponse
from backend.src.modules.n8n_inventory.application.use_cases import (
    list_inventory,
)
from backend.src.modules.n8n_inventory.infrastructure.n8n_client import (
    N8nApiClient,
)


router = APIRouter(prefix="/n8n-inventory", tags=["n8n-inventory"])


@router.get("/workflows", response_model=SuccessResponse[list])
async def list_n8n_inventory(
    db: DBSession,
    _current_user: CurrentUser = Depends(
        # Reuse the n8n_editor permission -- if you can open the iframe,
        # you can audit the workflow inventory. Read-only.
        PermissionChecker("n8n_editor", "access"),
    ),
):
    settings = get_settings()
    if not settings.N8N_API_KEY:
        raise HTTPException(
            status_code=503,
            detail="N8N_API_KEY not configured on the backend",
        )

    client = N8nApiClient(
        base_url=settings.N8N_API_BASE_URL,
        api_key=settings.N8N_API_KEY,
        verify_ssl=False,  # dev: self-signed nginx cert in the way
    )
    try:
        rows = await list_inventory(db=db, n8n_client=client)
    finally:
        await client.aclose()

    return SuccessResponse.ok(rows)
