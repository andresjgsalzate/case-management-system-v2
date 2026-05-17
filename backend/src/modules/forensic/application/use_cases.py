"""Forensic use cases — initial skeleton with READ operations.

This file is extended by Tasks 8-10 (launch_hunt, destructive governance,
cancel_hunt). Keep the surface API stable so the router (Task 14) can
depend on it incrementally.
"""
import logging

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.src.core.exceptions import BusinessRuleError, NotFoundError
from backend.src.modules.forensic.application.dtos import ClientSummary
from backend.src.modules.forensic.infrastructure.models import (
    ForensicArtifactModel,
)
from backend.src.modules.forensic.infrastructure.velo_client import (
    get_velo_client,
)
from backend.src.modules.tenants.infrastructure.models import TenantModel

logger = logging.getLogger(__name__)


class ForensicUseCases:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_artifacts(
        self,
        *,
        tenant_id: str,
        featured_only: bool = False,
        category: str | None = None,
        os: str | None = None,
        search: str | None = None,
        include_destructive: bool = False,
    ) -> list[ForensicArtifactModel]:
        """List artifacts visible to a tenant.

        Tenant scoping: rows with ``tenant_id == tenant_id`` OR ``tenant_id IS NULL``
        (the latter are "global" artifacts available to every tenant).

        Destructive artifacts are hidden unless ``include_destructive=True`` — the
        UI Hunt Launcher uses this flag so destructive operations are only
        surfaced through the n8n + approval flow, never the direct path.
        """
        stmt = select(ForensicArtifactModel).where(
            or_(
                ForensicArtifactModel.tenant_id == tenant_id,
                ForensicArtifactModel.tenant_id.is_(None),
            ),
            ForensicArtifactModel.is_active.is_(True),
        )
        if featured_only:
            stmt = stmt.where(ForensicArtifactModel.is_featured.is_(True))
        if category:
            stmt = stmt.where(ForensicArtifactModel.category == category)
        if os:
            stmt = stmt.where(ForensicArtifactModel.supported_os.contains([os]))
        if search:
            stmt = stmt.where(
                or_(
                    ForensicArtifactModel.name.ilike(f"%{search}%"),
                    ForensicArtifactModel.description.ilike(f"%{search}%"),
                )
            )
        if not include_destructive:
            stmt = stmt.where(ForensicArtifactModel.is_destructive.is_(False))

        stmt = stmt.order_by(
            ForensicArtifactModel.is_featured.desc(),
            ForensicArtifactModel.name.asc(),
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def list_clients(
        self,
        *,
        tenant_id: str,
        search: str | None = None,
        limit: int = 100,
    ) -> list[ClientSummary]:
        """List Velociraptor clients for a tenant (proxied to Velo)."""
        tenant = await self.db.get(TenantModel, tenant_id)
        if not tenant:
            raise NotFoundError(f"Tenant {tenant_id} not found")
        if not tenant.velo_org_id:
            raise BusinessRuleError(
                "Tenant has no Velociraptor org configured "
                "(velo_org_id is NULL)"
            )

        velo_client = get_velo_client()
        clients = await velo_client.list_clients(
            org_id=tenant.velo_org_id, label=None, limit=limit
        )

        if search:
            needle = search.lower()
            clients = [
                c for c in clients
                if needle in (c.get("hostname") or "").lower()
            ]
        return [ClientSummary(**c) for c in clients]
