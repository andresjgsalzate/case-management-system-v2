"""Use cases for the integrations module (Sub-spec 04).

Phase 1 scope: source CRUD + secret rotation. Webhook receive_event and async
process_event land in Tasks 9-10. Permission gates:
- create/update/delete/rotate → integrations:manage
- list/get                    → integrations:read
"""
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.src.core.exceptions import (
    NotFoundError,
    PermissionDeniedError,
)
from backend.src.modules.integrations.application.crypto import (
    encrypt_secret,
    generate_secret,
)
from backend.src.modules.integrations.application.dtos import (
    CreateSourcePayload,
    CreateSourceResponse,
    RotateSecretResponse,
    SourceResponse,
    UpdateSourcePayload,
)
from backend.src.modules.integrations.infrastructure.models import (
    IntegrationSourceModel,
    WazuhRuleTaxonomyMapModel,
)


def _wazuh_mapping_matches(
    mapping,
    rule_id: int | None,
    rule_groups: list[str],
    level: int | None,
) -> bool:
    """Pure-function predicate: does `mapping` apply to this Wazuh alert?

    Module-level (not a method) so unit tests can exercise each strategy
    without spinning up a use-case + DB.
    """
    strategy = mapping.match_strategy
    value = mapping.match_value or {}
    groups = set(rule_groups or [])

    if strategy == "rule_id":
        return rule_id is not None and rule_id == value.get("value")
    if strategy == "rule_groups_any":
        return bool(groups & set(value.get("groups") or []))
    if strategy == "rule_groups_all":
        required = set(value.get("groups") or [])
        return required.issubset(groups) if required else False
    if strategy == "level_min":
        return level is not None and level >= value.get("value", 0)
    if strategy == "level_range":
        if level is None:
            return False
        return value.get("min", 0) <= level <= value.get("max", 9999)
    return False  # Unknown strategy — silently skip rather than crash


class IntegrationsUseCases:
    def __init__(
        self,
        db: AsyncSession,
        taxonomies_uc=None,
        prioritization_uc=None,
        cases_uc=None,
        n8n_bridge_uc=None,
        automation_uc=None,
        events_bus=None,
    ):
        self.db = db
        self.taxonomies_uc = taxonomies_uc
        self.prioritization_uc = prioritization_uc
        self.cases_uc = cases_uc
        self.n8n_bridge_uc = n8n_bridge_uc
        self.automation_uc = automation_uc
        self.events_bus = events_bus

    # ── Permission gates ─────────────────────────────────────────────

    async def _require(self, actor, action: str) -> None:
        from backend.src.core.middleware.permission_checker import has_permission
        if not getattr(actor, "role_id", None):
            raise PermissionDeniedError(
                f"actor missing role_id for integrations:{action}",
            )
        ok = await has_permission(self.db, actor.role_id, "integrations", action)
        if not ok:
            raise PermissionDeniedError(f"integrations:{action} required")

    # ── Source CRUD ──────────────────────────────────────────────────

    async def create_source(
        self, *, actor, payload: CreateSourcePayload,
    ) -> CreateSourceResponse:
        """Create a new integration source and return the plaintext secret ONCE.

        The plaintext is generated server-side; the encrypted form is what
        persists. Clients must capture the value from this response — it
        is never echoed again.
        """
        await self._require(actor, "manage")
        plaintext = generate_secret()
        source = IntegrationSourceModel(
            tenant_id=payload.tenant_id,
            name=payload.name,
            source_type=payload.source_type,
            auth_method=payload.auth_method,
            auth_secret_encrypted=encrypt_secret(plaintext),
            auth_header_name=payload.auth_header_name,
            default_service_item_id=payload.default_service_item_id,
            default_priority_id=payload.default_priority_id,
            rate_limit_per_minute=payload.rate_limit_per_minute,
            created_by=actor.id,
        )
        self.db.add(source)
        await self.db.commit()
        await self.db.refresh(source)
        return CreateSourceResponse(
            source=SourceResponse.model_validate(source),
            plaintext_secret=plaintext,
            webhook_url=None,  # filled in by the router (it knows the public base URL)
        )

    async def update_source(
        self, *, actor, source_id: str, payload: UpdateSourcePayload,
    ) -> SourceResponse:
        await self._require(actor, "manage")
        source = await self._load_source(source_id)
        for field in (
            "name", "auth_header_name", "default_service_item_id",
            "default_priority_id", "rate_limit_per_minute", "is_active",
        ):
            value = getattr(payload, field)
            if value is not None:
                setattr(source, field, value)
        await self.db.commit()
        await self.db.refresh(source)
        return SourceResponse.model_validate(source)

    async def delete_source(self, *, actor, source_id: str) -> None:
        """Hard delete. inbound_events FK is RESTRICT, so this fails if any
        events exist for the source — callers should soft-deactivate instead."""
        await self._require(actor, "manage")
        source = await self._load_source(source_id)
        await self.db.delete(source)
        await self.db.commit()

    async def rotate_secret(
        self, *, actor, source_id: str,
    ) -> RotateSecretResponse:
        """Generate a new plaintext secret, persist its ciphertext, and return
        the plaintext ONCE. The previous secret stops authenticating immediately."""
        await self._require(actor, "manage")
        source = await self._load_source(source_id)
        plaintext = generate_secret()
        source.auth_secret_encrypted = encrypt_secret(plaintext)
        await self.db.commit()
        return RotateSecretResponse(
            source_id=source.id, plaintext_secret=plaintext,
        )

    # ── Reads ────────────────────────────────────────────────────────

    async def list_sources(self, *, actor) -> list[SourceResponse]:
        """Returns globals (tenant_id IS NULL) + own-tenant rows."""
        await self._require(actor, "read")
        stmt = (
            select(IntegrationSourceModel)
            .where(
                or_(
                    IntegrationSourceModel.tenant_id == actor.tenant_id,
                    IntegrationSourceModel.tenant_id.is_(None),
                ),
            )
            .order_by(IntegrationSourceModel.created_at.desc())
        )
        rows = (await self.db.execute(stmt)).scalars().all()
        return [SourceResponse.model_validate(r) for r in rows]

    async def get_source(self, *, actor, source_id: str) -> SourceResponse:
        await self._require(actor, "read")
        source = await self._load_source(source_id)
        return SourceResponse.model_validate(source)

    # ── Internal helpers ─────────────────────────────────────────────

    async def _load_source(self, source_id: str) -> IntegrationSourceModel:
        source = await self.db.get(IntegrationSourceModel, source_id)
        if not source:
            raise NotFoundError(f"integration_source {source_id} not found")
        return source

    # ── Wazuh taxonomy resolver ──────────────────────────────────────

    async def _resolve_wazuh_taxonomy(
        self,
        *,
        wazuh_rule_id: int | None,
        wazuh_rule_groups: list[str],
        wazuh_level: int | None,
        source_id: str,
        tenant_id: str | None,
    ):
        """Walk applicable wazuh_rule_to_taxonomy_map rows in priority order
        (priority DESC, then tenant DESC NULLS LAST so tenant overrides beat
        globals at equal priority). First strategy match wins; returns the
        SecurityTaxonomyModel or None if nothing matches."""
        stmt = (
            select(WazuhRuleTaxonomyMapModel)
            .where(
                WazuhRuleTaxonomyMapModel.is_active.is_(True),
                or_(
                    WazuhRuleTaxonomyMapModel.tenant_id == tenant_id,
                    WazuhRuleTaxonomyMapModel.tenant_id.is_(None),
                ),
                or_(
                    WazuhRuleTaxonomyMapModel.source_id == source_id,
                    WazuhRuleTaxonomyMapModel.source_id.is_(None),
                ),
            )
            .order_by(
                WazuhRuleTaxonomyMapModel.priority_order.desc(),
                WazuhRuleTaxonomyMapModel.tenant_id.desc().nulls_last(),
            )
        )
        mappings = (await self.db.execute(stmt)).scalars().all()

        for m in mappings:
            if _wazuh_mapping_matches(
                m, wazuh_rule_id, wazuh_rule_groups, wazuh_level,
            ):
                if not self.taxonomies_uc:
                    raise RuntimeError(
                        "taxonomies_uc not injected — cannot resolve taxonomy",
                    )
                return await self.taxonomies_uc.get_taxonomy_by_id(m.taxonomy_id)

        return None
