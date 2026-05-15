"""Security Taxonomy use cases.

Phase 1 (this commit) — READ paths only:
- list_taxonomies: own overrides + globals where override absent (DISTINCT ON tuic_code).
- get_taxonomy: lookup-with-fallback for (tuic_code, tenant_id).
- get_taxonomy_by_id: direct PK lookup.
- _load_for_update: SELECT FOR UPDATE for atomic operations.

Subsequent commits add CRUD, fork/refresh, notifications/mappings sub-ops.
"""
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.src.modules.security_taxonomies.infrastructure.models import (
    SecurityTaxonomyModel,
)


class SecurityTaxonomyUseCases:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ── READ ─────────────────────────────────────────────────────────────

    async def list_taxonomies(
        self,
        *,
        tenant_id: str,
        parent_id: str | None = None,
        search: str | None = None,
        include_inactive: bool = False,
    ) -> list[SecurityTaxonomyModel]:
        """Return taxonomies visible to a tenant: own overrides + globals.

        When a tenant override exists for a given tuic_code, the override hides
        the corresponding global. Implementation uses Postgres DISTINCT ON to pick
        the override per tuic_code, ordering tenant rows before NULLs.
        """
        # Build the visibility filter — own + globals
        filters = [
            or_(
                SecurityTaxonomyModel.tenant_id == tenant_id,
                SecurityTaxonomyModel.tenant_id.is_(None),
            )
        ]
        if not include_inactive:
            filters.append(SecurityTaxonomyModel.is_active.is_(True))
        if parent_id is not None:
            filters.append(SecurityTaxonomyModel.parent_id == parent_id)
        if search:
            term = f"%{search}%"
            filters.append(
                or_(
                    SecurityTaxonomyModel.tuic_code.ilike(term),
                    SecurityTaxonomyModel.name.ilike(term),
                )
            )

        # DISTINCT ON (tuic_code) ORDER BY tuic_code, tenant_id NULLS LAST
        # picks the tenant row when present, else the global row.
        stmt = (
            select(SecurityTaxonomyModel)
            .where(*filters)
            .order_by(
                SecurityTaxonomyModel.tuic_code,
                SecurityTaxonomyModel.tenant_id.desc().nulls_last(),
            )
            .distinct(SecurityTaxonomyModel.tuic_code)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_taxonomy(
        self, *, tuic_code: str, tenant_id: str
    ) -> SecurityTaxonomyModel | None:
        """Lookup by (tuic_code, tenant_id) with global fallback.

        Single query: WHERE tuic_code = X AND is_active AND (tenant_id = Y OR tenant_id IS NULL)
        ORDER BY tenant_id DESC NULLS LAST LIMIT 1 — picks override before global.
        """
        stmt = (
            select(SecurityTaxonomyModel)
            .where(
                SecurityTaxonomyModel.tuic_code == tuic_code,
                SecurityTaxonomyModel.is_active.is_(True),
                or_(
                    SecurityTaxonomyModel.tenant_id == tenant_id,
                    SecurityTaxonomyModel.tenant_id.is_(None),
                ),
            )
            .order_by(SecurityTaxonomyModel.tenant_id.desc().nulls_last())
            .limit(1)
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_taxonomy_by_id(
        self, taxonomy_id: str
    ) -> SecurityTaxonomyModel | None:
        """Direct primary-key lookup."""
        return await self.db.get(SecurityTaxonomyModel, taxonomy_id)

    async def _load_for_update(
        self, taxonomy_id: str
    ) -> SecurityTaxonomyModel | None:
        """SELECT FOR UPDATE — for atomic mutations in CRUD/fork/refresh."""
        stmt = (
            select(SecurityTaxonomyModel)
            .where(SecurityTaxonomyModel.id == taxonomy_id)
            .with_for_update()
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()
