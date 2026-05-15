"""Security Taxonomy use cases.

READ:
- list_taxonomies: own overrides + globals (DISTINCT ON tuic_code).
- get_taxonomy: lookup-with-fallback for (tuic_code, tenant_id).
- get_taxonomy_by_id: direct PK lookup.

WRITE (with audit log):
- create_taxonomy: permission-checked + uniqueness + parent validation + audit.
- update_taxonomy: idempotent diff-based + audit.
- soft_delete: validations (open cases, active descendants) + audit.

Audit log writes a row per CREATE/UPDATE/SOFT_DELETE with field-level diff (JSON).

Permission semantics:
- tenant_id=NULL (global) → requires 'manage_global'.
- tenant_id set → requires 'create' (or 'update'/'delete') AND
  (is_global role OR actor.tenant_id == taxonomy.tenant_id).
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.src.core.exceptions import (
    BusinessRuleError,
    ForbiddenError,
    NotFoundError,
    PermissionDeniedError,
    ValidationError,
)
from backend.src.core.middleware.permission_checker import has_permission
from backend.src.modules.security_taxonomies.application.dtos import (
    TaxonomyCreatePayload,
    TaxonomyUpdatePayload,
)
from backend.src.modules.security_taxonomies.infrastructure.models import (
    SecurityTaxonomyAuditLogModel,
    SecurityTaxonomyModel,
)


# Fields whose changes are tracked by audit log (excludes audit metadata itself).
_AUDITABLE_FIELDS: tuple[str, ...] = (
    "name", "description", "parent_id",
    "attack_type", "attack_subtype",
    "internal_impact_context", "external_impact_context",
    "managed_by_team_id",
    "default_case_type", "requires_ticket",
    "triage_mode", "delegated_workflow_id", "triage_timeout_seconds",
    "tlp_default", "prioritization_formula_id", "mitre_techniques",
    "is_active",
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

    # ── WRITE: create / update / soft_delete ─────────────────────────────

    async def create_taxonomy(
        self, *, actor, payload: TaxonomyCreatePayload
    ) -> SecurityTaxonomyModel:
        # 1. Permission check
        await self._require_write_permission(
            actor=actor, target_tenant_id=payload.tenant_id, action="create"
        )

        # 2. tuic_code uniqueness for (tenant_id, tuic_code)
        if await self._tuic_code_exists(payload.tenant_id, payload.tuic_code):
            raise ValidationError(
                f"tuic_code '{payload.tuic_code}' already exists for this tenant"
            )

        # 3. parent_id validation: parent must be global or in same tenant
        if payload.parent_id:
            parent = await self.get_taxonomy_by_id(payload.parent_id)
            if not parent:
                raise ValidationError(f"parent_id '{payload.parent_id}' not found")
            if parent.tenant_id is not None and parent.tenant_id != payload.tenant_id:
                raise ValidationError(
                    "parent_id belongs to a different tenant — not allowed"
                )

        # 4. Insert
        taxonomy = SecurityTaxonomyModel(
            id=str(uuid.uuid4()),
            tenant_id=payload.tenant_id,
            tuic_code=payload.tuic_code,
            name=payload.name,
            description=payload.description,
            parent_id=payload.parent_id,
            attack_type=payload.attack_type,
            attack_subtype=payload.attack_subtype,
            internal_impact_context=payload.internal_impact_context,
            external_impact_context=payload.external_impact_context,
            managed_by_team_id=payload.managed_by_team_id,
            default_case_type=payload.default_case_type,
            requires_ticket=payload.requires_ticket,
            triage_mode=payload.triage_mode,
            delegated_workflow_id=payload.delegated_workflow_id,
            triage_timeout_seconds=payload.triage_timeout_seconds,
            tlp_default=payload.tlp_default,
            prioritization_formula_id=payload.prioritization_formula_id,
            mitre_techniques=list(payload.mitre_techniques),
            created_by=actor.user_id,
        )
        self.db.add(taxonomy)
        await self.db.flush()

        # 5. Audit
        await self._log_audit(
            taxonomy_id=taxonomy.id,
            changed_by=actor.user_id,
            change_type="created",
            field_changes={
                "_full": {"from": None, "to": payload.model_dump(mode="json")}
            },
        )
        return taxonomy

    async def update_taxonomy(
        self, *, actor, taxonomy_id: str, updates: TaxonomyUpdatePayload
    ) -> SecurityTaxonomyModel:
        taxonomy = await self._load_for_update(taxonomy_id)
        if taxonomy is None:
            raise NotFoundError(f"Taxonomy {taxonomy_id} not found")

        await self._require_write_permission(
            actor=actor, target_tenant_id=taxonomy.tenant_id, action="update"
        )

        # Compute diff over auditable fields only
        update_dict = updates.model_dump(exclude_unset=True)
        changes: dict[str, dict] = {}
        for field, new_value in update_dict.items():
            if field not in _AUDITABLE_FIELDS:
                continue
            old_value = getattr(taxonomy, field)
            if old_value != new_value:
                changes[field] = {"from": old_value, "to": new_value}
                setattr(taxonomy, field, new_value)

        if not changes:
            return taxonomy  # idempotent: no audit row written

        taxonomy.updated_at = datetime.now(timezone.utc)
        taxonomy.updated_by = actor.user_id

        await self._log_audit(
            taxonomy_id=taxonomy.id,
            changed_by=actor.user_id,
            change_type="updated",
            field_changes=changes,
        )
        return taxonomy

    async def soft_delete(
        self, *, actor, taxonomy_id: str, reason: str
    ) -> None:
        if not reason or not reason.strip():
            raise ValidationError("'reason' is required for soft_delete")

        taxonomy = await self._load_for_update(taxonomy_id)
        if taxonomy is None:
            raise NotFoundError(f"Taxonomy {taxonomy_id} not found")

        await self._require_write_permission(
            actor=actor, target_tenant_id=taxonomy.tenant_id, action="delete"
        )

        # Validation 1: no open cases reference this taxonomy
        open_cases = await self._count_open_cases_with_taxonomy(taxonomy_id)
        if open_cases > 0:
            raise ValidationError(
                f"Cannot delete: {open_cases} open cases reference this taxonomy. "
                "Close them or reassign their taxonomy first."
            )

        # Validation 2: no active descendants
        if await self._has_active_descendants(taxonomy_id):
            raise ValidationError(
                "Cannot delete: this taxonomy has active descendants. "
                "Delete or reassign them first."
            )

        taxonomy.is_active = False
        taxonomy.updated_at = datetime.now(timezone.utc)
        taxonomy.updated_by = actor.user_id

        await self._log_audit(
            taxonomy_id=taxonomy.id,
            changed_by=actor.user_id,
            change_type="soft_deleted",
            field_changes={"is_active": {"from": True, "to": False}},
            reason=reason,
        )

    # ── Helpers ──────────────────────────────────────────────────────────

    async def _require_write_permission(
        self, *, actor, target_tenant_id: str | None, action: str
    ) -> None:
        """
        Global edits (target_tenant_id is None) require 'manage_global'.
        Tenant-scoped edits require the `action` permission AND tenant match
        (unless actor's role is is_global=True).
        """
        if target_tenant_id is None:
            ok = await has_permission(
                self.db, actor._role_id, "security_taxonomies", "manage_global"
            )
            if not ok:
                raise PermissionDeniedError(
                    "manage_global required to edit a global taxonomy"
                )
            return
        # Tenant-scoped
        ok = await has_permission(
            self.db, actor._role_id, "security_taxonomies", action
        )
        if not ok:
            raise PermissionDeniedError(
                f"security_taxonomies:{action} required"
            )
        # Tenant match check via role.is_global
        from sqlalchemy import text as _text
        row = (await self.db.execute(_text(
            "SELECT is_global FROM roles WHERE id = :rid"
        ), {"rid": actor._role_id})).first()
        is_global_role = bool(row[0]) if row else False
        if not is_global_role and getattr(actor, "tenant_id", None) != target_tenant_id:
            raise ForbiddenError(
                "Cannot edit taxonomy belonging to another tenant"
            )

    async def _tuic_code_exists(
        self, tenant_id: str | None, tuic_code: str
    ) -> bool:
        stmt = select(SecurityTaxonomyModel.id).where(
            SecurityTaxonomyModel.tuic_code == tuic_code,
        )
        if tenant_id is None:
            stmt = stmt.where(SecurityTaxonomyModel.tenant_id.is_(None))
        else:
            stmt = stmt.where(SecurityTaxonomyModel.tenant_id == tenant_id)
        return (await self.db.execute(stmt.limit(1))).scalar_one_or_none() is not None

    async def _count_open_cases_with_taxonomy(self, taxonomy_id: str) -> int:
        from sqlalchemy import func, text as _text
        # Use raw SQL to avoid importing CaseModel here (which would create a
        # cross-module dependency from a generic use case to a domain model).
        result = await self.db.execute(_text(
            "SELECT COUNT(*) FROM cases c "
            "LEFT JOIN case_statuses s ON s.id = c.status_id "
            "WHERE c.taxonomy_id = :tid "
            "AND (s.is_final IS NULL OR s.is_final = false)"
        ), {"tid": taxonomy_id})
        return int(result.scalar() or 0)

    async def _has_active_descendants(self, taxonomy_id: str) -> bool:
        stmt = select(SecurityTaxonomyModel.id).where(
            SecurityTaxonomyModel.parent_id == taxonomy_id,
            SecurityTaxonomyModel.is_active.is_(True),
        ).limit(1)
        return (await self.db.execute(stmt)).scalar_one_or_none() is not None

    async def _log_audit(
        self, *, taxonomy_id: str, changed_by: str, change_type: str,
        field_changes: dict, reason: str | None = None,
    ) -> None:
        # Coerce non-JSON types (datetime, UUID) so the JSON column accepts the dict.
        coerced = _coerce_json(field_changes)
        self.db.add(SecurityTaxonomyAuditLogModel(
            id=str(uuid.uuid4()),
            taxonomy_id=taxonomy_id,
            changed_by=changed_by,
            change_type=change_type,
            field_changes=coerced,
            reason=reason,
        ))


def _coerce_json(obj):
    """Recursively coerce datetime/UUID to ISO strings so JSON serializes cleanly."""
    if isinstance(obj, dict):
        return {k: _coerce_json(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_coerce_json(v) for v in obj]
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, uuid.UUID):
        return str(obj)
    return obj
