"""SOC Triage use cases (Phase 2 of docs/specs/triage.md).

Three public entry points:

  - create_triage    : add a new triage revision to a case
  - get_current      : latest revision of the case's triage (None if never triaged)
  - list_history     : every revision, ordered newest first

Priority calculation is inlined here (not delegated to the prioritization
module) because we have the exact 3-input matrix from the xlsx and the
inputs are user-supplied, not derived from case fields. Numeric scale +
weights live as module constants. Falso Positivo short-circuits the
formula entirely.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.src.core.exceptions import (
    NotFoundError,
    ValidationError,
)
from backend.src.modules.case_priorities.infrastructure.models import (
    CasePriorityModel,
)
from backend.src.modules.cases.infrastructure.models import CaseModel
from backend.src.modules.security_taxonomies.infrastructure.models import (
    SecurityTaxonomyModel,
)
from backend.src.modules.triage.application.dtos import CreateTriagePayload
from backend.src.modules.triage.infrastructure.models import (
    CaseTriageModel,
    TriageSlaPolicyModel,
)


# ─── Matrix constants (xlsx Priorización!R10-R13 + R24-R28) ──────────


# Per-level numeric value used in the weighted sum.
_LEVEL_VALUE: dict[str, int] = {
    "critico": 5,
    "alto": 4,
    "medio": 3,
    "bajo": 2,
}

# Matrix weights (sum = 1.0). Hardcoded to match the xlsx exactly; if
# this needs to be tenant-configurable, move into a settings row.
_WEIGHT_SEVERITY = Decimal("0.5")
_WEIGHT_IMPACT = Decimal("0.3")
_WEIGHT_CRITICALITY = Decimal("0.2")

# Score thresholds (>=) -> priority name. Mirrors xlsx ranges in
# Priorización!R10-R13 + spec section 3.3.
#
# NOTE on gender: xlsx uses masculine forms (Crítico/Alto/Medio/Bajo) on
# the severidad-de-alerta scale, but `case_priorities.name` rows are
# seeded in feminine to agree with the Spanish word "prioridad" (la
# prioridad es alta). We emit feminine names here so the
# `_lookup_priority_id` query finds the seeded rows.
def _score_to_priority_name(score: Decimal) -> str:
    if score >= Decimal("4.5"):
        return "Critica"
    if score >= Decimal("3.5"):
        return "Alta"
    if score >= Decimal("2.5"):
        return "Media"
    return "Baja"


# Fallback SLA defaults (in minutes) used when no row exists in
# triage_sla_policies for a given priority. Matches xlsx Priorización!R18-R22.
_FALLBACK_SLA: dict[str, int | None] = {
    "Critica":        20,
    "Alta":           40,
    "Media":          120,
    "Baja":           720,            # 12h
    "Falso Positivo": None,           # N/A
}


class TriageUseCases:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ── PUBLIC API ──────────────────────────────────────────────────

    async def get_current(self, case_id: str) -> CaseTriageModel | None:
        """Latest triage revision for the case, or None if never triaged."""
        stmt = (
            select(CaseTriageModel)
            .where(CaseTriageModel.case_id == case_id)
            .order_by(desc(CaseTriageModel.version))
            .limit(1)
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def list_history(self, case_id: str) -> list[CaseTriageModel]:
        stmt = (
            select(CaseTriageModel)
            .where(CaseTriageModel.case_id == case_id)
            .order_by(desc(CaseTriageModel.version))
        )
        return list((await self.db.execute(stmt)).scalars().all())

    async def create_triage(
        self,
        *,
        case_id: str,
        actor_user_id: str,
        payload: CreateTriagePayload,
    ) -> CaseTriageModel:
        # 1. Load + validate case
        case = await self.db.get(CaseModel, case_id)
        if case is None:
            raise NotFoundError(f"Case {case_id} not found")

        # 2. Load + validate sub-taxonomy
        sub = await self.db.get(SecurityTaxonomyModel, payload.sub_taxonomy_id)
        if sub is None:
            raise NotFoundError(
                f"Sub-taxonomy {payload.sub_taxonomy_id} not found"
            )

        # 3. Validate attachments belong to this case (if supplied)
        for att_id in (payload.evidence_attachment_id, payload.behavior_attachment_id):
            if att_id:
                await self._validate_attachment(att_id, case_id)

        # 4. Resolve Impacto potencial from sub-taxonomy + context origin
        impact_slug = self._resolve_impact(sub, payload.context_origin_type)

        # 5. Compute score + priority + SLA
        priority_name, score, sla_minutes = await self._compute_priority(
            severity=payload.alert_severity,
            impact_slug=impact_slug,
            criticality=payload.asset_criticality,
        )

        # 6. Resolve priority FK from name (case_priorities.name lookup)
        priority_id = await self._lookup_priority_id(
            priority_name, tenant_id=case.tenant_id,
        )

        # 7. Snapshot tenant name (best-effort -- if no tenants table row, leave NULL)
        tenant_name = await self._resolve_tenant_name(case.tenant_id)

        # 8. Determine next version number for this case
        next_version = await self._next_version(case_id)

        # 9. Insert triage
        triage = CaseTriageModel(
            case_id=case_id,
            version=next_version,
            triaged_by_user_id=actor_user_id,
            case_title_snapshot=case.title,
            case_tenant_name_snapshot=tenant_name,
            sub_taxonomy_id=payload.sub_taxonomy_id,
            alert_severity=payload.alert_severity,
            context_origin_type=payload.context_origin_type,
            asset_criticality=payload.asset_criticality,
            tool_type_id=payload.tool_type_id,
            tool_action_id=payload.tool_action_id,
            context_origin_detail=payload.context_origin_detail,
            related_asset=payload.related_asset,
            alert_duration_seconds=payload.alert_duration_seconds,
            alert_repetitions=payload.alert_repetitions,
            analysis_narrative=payload.analysis_narrative,
            behavior_narrative=payload.behavior_narrative,
            recommendations=payload.recommendations,
            evidence_attachment_id=payload.evidence_attachment_id,
            behavior_attachment_id=payload.behavior_attachment_id,
            calculated_priority_id=priority_id,
            calculated_score=score,
            calculated_sla_minutes=sla_minutes,
        )
        self.db.add(triage)
        await self.db.flush()

        # 10. Update case.priority_id so the rest of the system sees the
        # triage-driven priority. Only when we resolved a priority row;
        # otherwise leave the case priority untouched (e.g. FP without a
        # seeded "Falso Positivo" priority row).
        if priority_id:
            case.priority_id = priority_id

        return triage

    # ── INTERNAL HELPERS ────────────────────────────────────────────

    async def _validate_attachment(self, att_id: str, case_id: str) -> None:
        """Defensive: ensure the attachment belongs to the same case so we
        can't accidentally link evidence from another case's upload.
        """
        from backend.src.modules.attachments.infrastructure.models import (
            CaseAttachmentModel,
        )
        att = await self.db.get(CaseAttachmentModel, att_id)
        if att is None:
            raise NotFoundError(f"Attachment {att_id} not found")
        if att.case_id != case_id:
            raise ValidationError(
                f"Attachment {att_id} does not belong to case {case_id}"
            )

    def _resolve_impact(
        self,
        sub: SecurityTaxonomyModel,
        context: str,
    ) -> str | None:
        """Per spec section 2.1: pick the internal vs external impact
        of the sub-taxonomy based on the origin context.
        """
        if context == "origen_interno":
            return sub.internal_impact_context
        return sub.external_impact_context

    async def _compute_priority(
        self,
        *,
        severity: str,
        impact_slug: str | None,
        criticality: str,
    ) -> tuple[str, Decimal, int | None]:
        """Returns (priority_name, score, sla_minutes).

        Falso Positivo is a special case: skip matrix entirely, return
        ("Falso Positivo", 0, None). Matches xlsx + spec section 3.2.

        For the regular matrix, missing impact (None / unknown slug) is
        treated as "bajo" (lowest score 2) so the calculation doesn't
        crash on under-configured taxonomies. The UI should warn before
        save when impact is unresolved.
        """
        if severity == "falso_positivo":
            sla = await self._lookup_sla_minutes("Falso Positivo")
            if sla is None:
                sla = _FALLBACK_SLA["Falso Positivo"]
            return ("Falso Positivo", Decimal("0"), sla)

        sev_val = _LEVEL_VALUE.get(severity, 2)
        imp_val = _LEVEL_VALUE.get(impact_slug or "bajo", 2)
        crit_val = _LEVEL_VALUE.get(criticality, 2)

        # Weighted sum -> 2 decimal places (matches DB numeric(4,2))
        score = (
            Decimal(sev_val) * _WEIGHT_SEVERITY
            + Decimal(imp_val) * _WEIGHT_IMPACT
            + Decimal(crit_val) * _WEIGHT_CRITICALITY
        ).quantize(Decimal("0.01"))

        priority_name = _score_to_priority_name(score)

        # SLA lookup: prefer triage_sla_policies row, fallback to constants.
        sla = await self._lookup_sla_minutes(priority_name)
        if sla is None and priority_name in _FALLBACK_SLA:
            sla = _FALLBACK_SLA[priority_name]
        return (priority_name, score, sla)

    async def _lookup_priority_id(
        self, priority_name: str, *, tenant_id: str | None,
    ) -> str | None:
        """Resolve case_priorities.id by name (tenant-scoped + global fallback)."""
        stmt = (
            select(CasePriorityModel)
            .where(CasePriorityModel.name == priority_name)
            .where(CasePriorityModel.is_active.is_(True))
        )
        rows = list((await self.db.execute(stmt)).scalars().all())
        if not rows:
            return None
        # Prefer tenant-specific row; fall back to global (tenant_id IS NULL).
        for r in rows:
            if r.tenant_id == tenant_id:
                return r.id
        for r in rows:
            if r.tenant_id is None:
                return r.id
        return rows[0].id

    async def _lookup_sla_minutes(self, priority_name: str) -> int | None:
        """Lookup SLA from triage_sla_policies via priority name -> priority_id chain."""
        # First resolve priority id (any tenant) by name
        pstmt = select(CasePriorityModel.id).where(
            CasePriorityModel.name == priority_name
        )
        pid = (await self.db.execute(pstmt)).scalar_one_or_none()
        if pid is None:
            return None
        sstmt = select(TriageSlaPolicyModel.sla_minutes).where(
            TriageSlaPolicyModel.priority_id == pid,
            TriageSlaPolicyModel.is_active.is_(True),
        ).limit(1)
        return (await self.db.execute(sstmt)).scalar_one_or_none()

    async def _resolve_tenant_name(self, tenant_id: str | None) -> str | None:
        if not tenant_id:
            return None
        from sqlalchemy import text as _text
        row = (await self.db.execute(
            _text("SELECT name FROM tenants WHERE id = :tid"),
            {"tid": tenant_id},
        )).first()
        return row[0] if row else None

    async def _next_version(self, case_id: str) -> int:
        from sqlalchemy import func
        stmt = select(func.coalesce(func.max(CaseTriageModel.version), 0)).where(
            CaseTriageModel.case_id == case_id
        )
        current = (await self.db.execute(stmt)).scalar_one()
        return int(current) + 1

    # ── Context enrichment for "current triage" endpoint ────────────

    async def enrich_with_context(
        self, triage: CaseTriageModel,
    ) -> dict[str, Any]:
        """Returns a dict suitable for TriageWithContext: triage row plus
        parent taxonomy + resolved impact.
        """
        sub = await self.db.get(SecurityTaxonomyModel, triage.sub_taxonomy_id)
        parent = None
        if sub and sub.parent_id:
            parent = await self.db.get(SecurityTaxonomyModel, sub.parent_id)

        impact = (
            self._resolve_impact(sub, triage.context_origin_type) if sub else None
        )
        return {
            "triage": triage,
            "parent_taxonomy_id": parent.id if parent else (sub.id if sub else None),
            "parent_taxonomy_name": parent.name if parent else (sub.name if sub else None),
            "sub_taxonomy_name": sub.name if sub else "(eliminada)",
            "impacto_potencial": impact,
        }
