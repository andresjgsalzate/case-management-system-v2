"""n8n inventory: live n8n workflows joined with the CMS catalog.

Two sources, one view:
- n8n REST API (`workflows`): every workflow that exists in n8n,
  registered or not.
- CMS `n8n_workflows` table: subset the SOC catalogued as runnable
  playbooks (with approval / role gating).

Match strategy: explicit `n8n_workflow_id` column on the CMS row.
Rows without that link are not joined even if names coincide -- name
matching is too noisy in practice (duplicates, renames). Operator (or
WCR implement action) populates the link as workflows get registered.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.src.modules.n8n_bridge.infrastructure.models import (
    N8nWorkflowModel,
)
from backend.src.modules.n8n_inventory.infrastructure.n8n_client import (
    N8nApiClient,
)


def _catalog_row_to_dict(row: N8nWorkflowModel) -> dict[str, Any]:
    return {
        "id": row.id,
        "tenant_id": row.tenant_id,
        "name": row.name,
        "description": row.description,
        "workflow_url": row.workflow_url,
        "is_active": row.is_active,
        "requires_approval": row.requires_approval,
        "allowed_role_ids": row.allowed_role_ids,
    }


async def list_inventory(
    *, db: AsyncSession, n8n_client: N8nApiClient
) -> list[dict[str, Any]]:
    """Merge live n8n workflows with the CMS catalog.

    Returns one entry per n8n workflow, plus catalog-only rows whose
    `n8n_workflow_id` no longer exists in n8n (stale link warning).

    Each entry shape:
        {
          "n8n_id": "F7v469lghiBA7FcX" | None,
          "n8n_name": "Slack Alert" | None,
          "n8n_active": true | false | None,
          "catalog": { ...catalog row... } | None,
          "status": "registered" | "orphan_in_n8n" | "orphan_in_cms",
        }
    """
    n8n_workflows = await n8n_client.list_workflows()

    catalog_rows = (
        await db.execute(select(N8nWorkflowModel))
    ).scalars().all()
    catalog_by_n8n_id: dict[str, N8nWorkflowModel] = {
        r.n8n_workflow_id: r for r in catalog_rows if r.n8n_workflow_id
    }
    catalog_unmatched = [r for r in catalog_rows if not r.n8n_workflow_id]

    out: list[dict[str, Any]] = []
    seen_n8n_ids: set[str] = set()

    for wf in n8n_workflows:
        n8n_id = str(wf.get("id", ""))
        if not n8n_id:
            continue
        seen_n8n_ids.add(n8n_id)
        catalog = catalog_by_n8n_id.get(n8n_id)
        out.append(
            {
                "n8n_id": n8n_id,
                "n8n_name": wf.get("name"),
                "n8n_active": wf.get("active"),
                "n8n_updated_at": wf.get("updatedAt"),
                "catalog": _catalog_row_to_dict(catalog) if catalog else None,
                "status": "registered" if catalog else "orphan_in_n8n",
            }
        )

    # Catalog rows linked to an n8n id that no longer exists in n8n.
    for n8n_id, catalog in catalog_by_n8n_id.items():
        if n8n_id not in seen_n8n_ids:
            out.append(
                {
                    "n8n_id": n8n_id,
                    "n8n_name": None,
                    "n8n_active": None,
                    "n8n_updated_at": None,
                    "catalog": _catalog_row_to_dict(catalog),
                    "status": "orphan_in_cms",
                }
            )

    # Catalog rows with no n8n_workflow_id link at all -- legacy entries
    # that should be matched up manually or via the WCR implement flow.
    for catalog in catalog_unmatched:
        out.append(
            {
                "n8n_id": None,
                "n8n_name": None,
                "n8n_active": None,
                "n8n_updated_at": None,
                "catalog": _catalog_row_to_dict(catalog),
                "status": "unlinked",
            }
        )

    return out
