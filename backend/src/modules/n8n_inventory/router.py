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


@router.get(
    "/workflows/{n8n_id}/webhooks",
    response_model=SuccessResponse[list[dict]],
)
async def list_workflow_webhooks(
    n8n_id: str,
    _current_user: CurrentUser = Depends(
        PermissionChecker("n8n_editor", "access"),
    ),
):
    """Inspect an n8n workflow and return its webhook entry points.

    Used by the "Registrar orphan" flow to pre-fill workflow_url
    without forcing the operator to dig into the editor. Returns
    one entry per webhook node:

      [{ "path": "abc-123", "url": "https://.../webhook/abc-123",
         "http_method": "POST", "node_name": "Webhook" }, ...]

    Empty list means the workflow has no webhook trigger (it runs
    on schedule, manual, internal event, etc.) -- the operator
    will need to type the URL manually or skip registration.
    """
    settings = get_settings()
    if not settings.N8N_API_KEY:
        raise HTTPException(
            status_code=503,
            detail="N8N_API_KEY not configured on the backend",
        )

    client = N8nApiClient(
        base_url=settings.N8N_API_BASE_URL,
        api_key=settings.N8N_API_KEY,
        verify_ssl=False,
    )
    try:
        wf = await client.get_workflow(n8n_id)
    finally:
        await client.aclose()

    if wf is None:
        raise HTTPException(status_code=404, detail="n8n workflow not found")

    base = settings.N8N_WEBHOOK_BASE.rstrip("/") + "/"
    out: list[dict] = []
    for node in wf.get("nodes", []):
        node_type = node.get("type", "")
        # n8n's webhook-capable triggers all expose `path` + `httpMethod`
        # under parameters. formTrigger + chatTrigger reuse the same
        # convention. Skip anything else (schedule, manual, etc.).
        if node_type not in (
            "n8n-nodes-base.webhook",
            "n8n-nodes-base.formTrigger",
            "@n8n/n8n-nodes-langchain.chatTrigger",
        ):
            continue
        params = node.get("parameters") or {}
        path = params.get("path") or node.get("webhookId")
        if not path:
            continue
        out.append({
            "path": str(path),
            "url": base + str(path).lstrip("/"),
            "http_method": params.get("httpMethod", "POST"),
            "node_name": node.get("name", ""),
            "node_type": node_type,
        })

    return SuccessResponse.ok(out)
