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
    CatalogMappingCreatePayload,
    NotificationCreatePayload,
    TaxonomyCreatePayload,
    TaxonomyUpdatePayload,
)
from backend.src.modules.security_taxonomies.infrastructure.models import (
    SecurityTaxonomyAuditLogModel,
    SecurityTaxonomyModel,
    TaxonomyCatalogMappingModel,
    TaxonomyNotificationModel,
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

# Fields copied from source to fork (or re-applied on refresh_from_global).
# Excludes: id, tenant_id, tuic_code (immutable identity), audit fields,
# fork-tracking fields (managed by fork/refresh itself).
_CLONABLE_FIELDS: tuple[str, ...] = (
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

    # ── WRITE: fork / refresh ────────────────────────────────────────────

    async def fork_to_tenant(
        self, *, actor, global_taxonomy_id: str, target_tenant_id: str
    ) -> SecurityTaxonomyModel:
        """Clone a global taxonomy into a tenant-specific override.

        Copies all _CLONABLE_FIELDS + N:M relations (notifications + catalog mappings),
        sets forked_from_global_id and forked_from_global_at. Rejected if:
          - source is not global (tenant_id IS NULL)
          - target tenant already has an override for this tuic_code (or already
            has a fork from this exact source)
        """
        from sqlalchemy import text as _text

        source = await self.get_taxonomy_by_id(global_taxonomy_id)
        if source is None:
            raise NotFoundError(f"Taxonomy {global_taxonomy_id} not found")
        if source.tenant_id is not None:
            raise ValidationError("Only global taxonomies can be forked")

        # Permission: forking creates a tenant-scoped row → 'create' perm
        await self._require_write_permission(
            actor=actor, target_tenant_id=target_tenant_id, action="create"
        )

        # Idempotency: reject if target tenant already has this tuic_code
        if await self._tuic_code_exists(target_tenant_id, source.tuic_code):
            raise ValidationError(
                f"Tenant '{target_tenant_id}' already has an override for "
                f"tuic_code '{source.tuic_code}'"
            )

        forked = SecurityTaxonomyModel(
            id=str(uuid.uuid4()),
            tenant_id=target_tenant_id,
            tuic_code=source.tuic_code,
            forked_from_global_id=source.id,
            forked_from_global_at=datetime.now(timezone.utc),
            created_by=actor.user_id,
        )
        for field in _CLONABLE_FIELDS:
            setattr(forked, field, getattr(source, field))
        self.db.add(forked)
        await self.db.flush()

        # Clone N:M children (notifications + catalog_mappings)
        await self.db.execute(_text(
            "INSERT INTO taxonomy_notifications "
            "(id, taxonomy_id, team_id, notify_phase, notify_channel, escalation_minutes) "
            "SELECT gen_random_uuid()::text, :forked_id, team_id, notify_phase, "
            "       notify_channel, escalation_minutes "
            "FROM taxonomy_notifications WHERE taxonomy_id = :src_id"
        ), {"forked_id": forked.id, "src_id": source.id})
        await self.db.execute(_text(
            "INSERT INTO taxonomy_catalog_mappings "
            "(id, taxonomy_id, service_catalog_item_id, is_default, priority_order) "
            "SELECT gen_random_uuid()::text, :forked_id, service_catalog_item_id, "
            "       is_default, priority_order "
            "FROM taxonomy_catalog_mappings WHERE taxonomy_id = :src_id"
        ), {"forked_id": forked.id, "src_id": source.id})

        await self._log_audit(
            taxonomy_id=forked.id,
            changed_by=actor.user_id,
            change_type="forked",
            field_changes={"_forked_from": {"from": None, "to": source.id}},
        )
        return forked

    async def refresh_from_global(
        self, *, actor, taxonomy_id: str
    ) -> SecurityTaxonomyModel:
        """Re-sync a tenant fork with the current global state.

        Overwrites _CLONABLE_FIELDS with the current values from
        forked_from_global_id. Updates forked_from_global_at to mark a fresh sync.
        Refresh of N:M children would require explicit semantics
        (delete+reinsert vs merge) — deferred to a later sub-task.
        """
        forked = await self._load_for_update(taxonomy_id)
        if forked is None:
            raise NotFoundError(f"Taxonomy {taxonomy_id} not found")
        if forked.tenant_id is None:
            raise ValidationError("Cannot refresh — this is a global taxonomy")
        if forked.forked_from_global_id is None:
            raise ValidationError(
                "Cannot refresh — taxonomy is not forked from a global parent"
            )

        await self._require_write_permission(
            actor=actor, target_tenant_id=forked.tenant_id, action="update"
        )

        source = await self.get_taxonomy_by_id(forked.forked_from_global_id)
        if source is None:
            raise ValidationError(
                "Global parent no longer exists; cannot refresh."
            )

        # Compute diff for audit; apply on fields that actually differ
        changes: dict[str, dict] = {}
        for field in _CLONABLE_FIELDS:
            old_value = getattr(forked, field)
            new_value = getattr(source, field)
            if old_value != new_value:
                changes[field] = {"from": old_value, "to": new_value}
                setattr(forked, field, new_value)

        forked.forked_from_global_at = datetime.now(timezone.utc)
        forked.updated_at = datetime.now(timezone.utc)
        forked.updated_by = actor.user_id

        await self._log_audit(
            taxonomy_id=forked.id,
            changed_by=actor.user_id,
            change_type="refreshed_from_global",
            field_changes=changes,
        )
        return forked

    async def list_audit_log(
        self,
        *,
        taxonomy_id: str,
        change_type: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        limit: int = 50,
    ) -> list[SecurityTaxonomyAuditLogModel]:
        """Audit log entries for a taxonomy with optional filters.

        Permission gating is expected at the router layer (read_audit_log).
        Returns newest-first.
        """
        stmt = select(SecurityTaxonomyAuditLogModel).where(
            SecurityTaxonomyAuditLogModel.taxonomy_id == taxonomy_id
        )
        if change_type:
            stmt = stmt.where(
                SecurityTaxonomyAuditLogModel.change_type == change_type
            )
        if date_from is not None:
            stmt = stmt.where(
                SecurityTaxonomyAuditLogModel.changed_at >= date_from
            )
        if date_to is not None:
            stmt = stmt.where(
                SecurityTaxonomyAuditLogModel.changed_at <= date_to
            )
        stmt = stmt.order_by(
            SecurityTaxonomyAuditLogModel.changed_at.desc()
        ).limit(limit)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def is_outdated_vs_global(
        self, taxonomy: SecurityTaxonomyModel
    ) -> bool:
        """True if this is a fork AND the global parent updated after the last sync."""
        if taxonomy.forked_from_global_id is None:
            return False
        source = await self.get_taxonomy_by_id(taxonomy.forked_from_global_id)
        if source is None:
            return False
        if taxonomy.forked_from_global_at is None:
            return True
        return source.updated_at > taxonomy.forked_from_global_at

    # ── WRITE: notifications + catalog mappings sub-ops ──────────────────

    async def add_notification(
        self, *, actor, taxonomy_id: str, payload: NotificationCreatePayload
    ) -> TaxonomyNotificationModel:
        taxonomy = await self._load_for_update(taxonomy_id)
        if taxonomy is None:
            raise NotFoundError(f"Taxonomy {taxonomy_id} not found")
        await self._require_write_permission(
            actor=actor, target_tenant_id=taxonomy.tenant_id, action="update"
        )
        # Uniqueness check (also enforced by DB constraint, but raise
        # ValidationError instead of IntegrityError for cleaner API).
        existing = (await self.db.execute(
            select(TaxonomyNotificationModel.id).where(
                TaxonomyNotificationModel.taxonomy_id == taxonomy_id,
                TaxonomyNotificationModel.team_id == payload.team_id,
                TaxonomyNotificationModel.notify_phase == payload.notify_phase,
            )
        )).scalar_one_or_none()
        if existing:
            raise ValidationError(
                f"Notification already exists for taxonomy {taxonomy_id}, "
                f"team {payload.team_id}, phase '{payload.notify_phase}'"
            )
        notif = TaxonomyNotificationModel(
            id=str(uuid.uuid4()),
            taxonomy_id=taxonomy_id,
            team_id=payload.team_id,
            notify_phase=payload.notify_phase,
            notify_channel=payload.notify_channel,
            escalation_minutes=payload.escalation_minutes,
        )
        self.db.add(notif)
        await self.db.flush()
        return notif

    async def remove_notification(
        self, *, actor, notification_id: str
    ) -> None:
        notif = await self.db.get(TaxonomyNotificationModel, notification_id)
        if notif is None:
            raise NotFoundError(f"Notification {notification_id} not found")
        taxonomy = await self.get_taxonomy_by_id(notif.taxonomy_id)
        if taxonomy is None:
            # Defensive: should never happen due to FK, but guard anyway.
            raise NotFoundError("Parent taxonomy not found")
        await self._require_write_permission(
            actor=actor, target_tenant_id=taxonomy.tenant_id, action="update"
        )
        await self.db.delete(notif)
        await self.db.flush()

    async def add_catalog_mapping(
        self, *, actor, taxonomy_id: str, payload: CatalogMappingCreatePayload
    ) -> TaxonomyCatalogMappingModel:
        taxonomy = await self._load_for_update(taxonomy_id)
        if taxonomy is None:
            raise NotFoundError(f"Taxonomy {taxonomy_id} not found")
        await self._require_write_permission(
            actor=actor, target_tenant_id=taxonomy.tenant_id, action="update"
        )
        existing = (await self.db.execute(
            select(TaxonomyCatalogMappingModel.id).where(
                TaxonomyCatalogMappingModel.taxonomy_id == taxonomy_id,
                TaxonomyCatalogMappingModel.service_catalog_item_id
                == payload.service_catalog_item_id,
            )
        )).scalar_one_or_none()
        if existing:
            raise ValidationError(
                f"Mapping already exists for taxonomy {taxonomy_id} and "
                f"service item {payload.service_catalog_item_id}"
            )
        # If marking as default, unset any previous default for this taxonomy
        if payload.is_default:
            await self._unset_default_mappings(taxonomy_id, exclude_mapping_id=None)
        mapping = TaxonomyCatalogMappingModel(
            id=str(uuid.uuid4()),
            taxonomy_id=taxonomy_id,
            service_catalog_item_id=payload.service_catalog_item_id,
            is_default=payload.is_default,
            priority_order=payload.priority_order,
        )
        self.db.add(mapping)
        await self.db.flush()
        return mapping

    async def set_default_catalog_mapping(
        self, *, actor, mapping_id: str
    ) -> TaxonomyCatalogMappingModel:
        mapping = await self.db.get(TaxonomyCatalogMappingModel, mapping_id)
        if mapping is None:
            raise NotFoundError(f"Mapping {mapping_id} not found")
        taxonomy = await self._load_for_update(mapping.taxonomy_id)
        if taxonomy is None:
            raise NotFoundError("Parent taxonomy not found")
        await self._require_write_permission(
            actor=actor, target_tenant_id=taxonomy.tenant_id, action="update"
        )
        # Atomic: unset others, set this one — DB partial unique index on
        # (taxonomy_id WHERE is_default=true) enforces invariant, but unset
        # FIRST to avoid transient violation during UPDATE.
        await self._unset_default_mappings(
            mapping.taxonomy_id, exclude_mapping_id=mapping_id,
        )
        mapping.is_default = True
        await self.db.flush()
        return mapping

    async def remove_catalog_mapping(
        self, *, actor, mapping_id: str
    ) -> None:
        mapping = await self.db.get(TaxonomyCatalogMappingModel, mapping_id)
        if mapping is None:
            raise NotFoundError(f"Mapping {mapping_id} not found")
        taxonomy = await self.get_taxonomy_by_id(mapping.taxonomy_id)
        if taxonomy is None:
            raise NotFoundError("Parent taxonomy not found")
        await self._require_write_permission(
            actor=actor, target_tenant_id=taxonomy.tenant_id, action="update"
        )
        await self.db.delete(mapping)
        await self.db.flush()

    async def list_catalog_mappings(
        self, taxonomy_id: str
    ) -> list[TaxonomyCatalogMappingModel]:
        """Return every catalog mapping for a taxonomy ordered by
        (is_default desc, priority_order asc). Read-only — caller still
        needs the taxonomy:read permission via the router dep."""
        result = await self.db.execute(
            select(TaxonomyCatalogMappingModel)
            .where(TaxonomyCatalogMappingModel.taxonomy_id == taxonomy_id)
            .order_by(
                TaxonomyCatalogMappingModel.is_default.desc(),
                TaxonomyCatalogMappingModel.priority_order.asc(),
            )
        )
        return list(result.scalars().all())

    async def _unset_default_mappings(
        self, taxonomy_id: str, *, exclude_mapping_id: str | None
    ) -> None:
        from sqlalchemy import update as _update
        stmt = (
            _update(TaxonomyCatalogMappingModel)
            .where(
                TaxonomyCatalogMappingModel.taxonomy_id == taxonomy_id,
                TaxonomyCatalogMappingModel.is_default.is_(True),
            )
            .values(is_default=False)
        )
        if exclude_mapping_id is not None:
            stmt = stmt.where(
                TaxonomyCatalogMappingModel.id != exclude_mapping_id
            )
        await self.db.execute(stmt)

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
                self.db, actor.role_id, "security_taxonomies", "manage_global"
            )
            if not ok:
                raise PermissionDeniedError(
                    "manage_global required to edit a global taxonomy"
                )
            return
        # Tenant-scoped
        ok = await has_permission(
            self.db, actor.role_id, "security_taxonomies", action
        )
        if not ok:
            raise PermissionDeniedError(
                f"security_taxonomies:{action} required"
            )
        # Tenant match check via role.is_global
        from sqlalchemy import text as _text
        row = (await self.db.execute(_text(
            "SELECT is_global FROM roles WHERE id = :rid"
        ), {"rid": actor.role_id})).first()
        is_global_role = bool(row[0]) if row else False
        if not is_global_role and getattr(actor, "tenant_id", None) != target_tenant_id:
            raise ForbiddenError(
                "Cannot edit taxonomy belonging to another tenant"
            )

    async def _tuic_code_exists(
        self, tenant_id: str | None, tuic_code: str
    ) -> bool:
        # Only active rows count for uniqueness -- soft-deleted taxonomies
        # release their tuic_code so it can be reused. Mirrors the partial
        # unique index uq_taxonomy_tenant_tuic_active (Alembic d9a8c1f6e4b2).
        stmt = select(SecurityTaxonomyModel.id).where(
            SecurityTaxonomyModel.tuic_code == tuic_code,
            SecurityTaxonomyModel.is_active.is_(True),
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
