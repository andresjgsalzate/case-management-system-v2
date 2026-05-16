"""Prioritization use cases.

This file ships incrementally:
- Task 4: __init__ + _resolve_criterion_value (data_source dispatch).
- Task 5: calculate_priority (happy path).
- Task 6: missing-data strategies (skip / use_default / error).
- Task 7: multi-tenant formula resolution.
- Task 8: create_formula_version.
- Task 10: manual_recalculation + history.
"""
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.src.modules.prioritization.application.derived_handlers import (
    DERIVED_HANDLERS,
    DerivedResult,
)
from backend.src.modules.prioritization.infrastructure.models import (
    PrioritizationCriterionModel,
    PrioritizationScaleModel,
)


# Map TLP labels to numeric scores (for criteria with source_field_key='tlp_default').
_TLP_NUMERIC = {"white": 1, "green": 2, "amber": 3, "red": 5}


class PrioritizationUseCases:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ── Criterion value resolution ───────────────────────────────────────

    async def _resolve_criterion_value(
        self, case, criterion: PrioritizationCriterionModel,
    ) -> tuple[int | None, str | None, str]:
        """Returns (numeric_value, label, source_description).

        Returns (None, None, reason) when data is unavailable — caller decides
        what to do (use_default / skip / error) based on criterion.missing_data_strategy.
        """
        ds = criterion.data_source

        if ds == "taxonomy_field":
            return await self._resolve_taxonomy_field(case, criterion)

        if ds == "case_custom_value":
            return await self._resolve_case_custom_value(case, criterion)

        if ds == "asset_field":
            # Asset resolution requires applications module — out of scope
            # for this task; placeholder returns "no_asset" so missing strategy
            # kicks in.
            return None, None, "no_asset"

        if ds == "manual_input":
            # Operator must have provided at creation; not auto-resolvable here.
            return None, None, "not_provided"

        if ds == "derived":
            handler = DERIVED_HANDLERS.get(criterion.source_field_key or "")
            if not handler:
                return None, None, "no_handler"
            result: DerivedResult = await handler(case, self.db)
            return result.value, result.label, f"derived.{criterion.source_field_key}"

        return None, None, "unknown_data_source"

    async def _resolve_taxonomy_field(
        self, case, criterion: PrioritizationCriterionModel,
    ) -> tuple[int | None, str | None, str]:
        if not case.taxonomy_id:
            return None, None, "no_taxonomy"

        from backend.src.modules.security_taxonomies.infrastructure.models import (
            SecurityTaxonomyModel,
        )
        taxonomy = await self.db.get(SecurityTaxonomyModel, case.taxonomy_id)
        if not taxonomy:
            return None, None, "no_taxonomy"

        key = criterion.source_field_key
        # Special-case the well-known mappings the seed defines.
        if key == "tlp_default":
            label = taxonomy.tlp_default
            value = _TLP_NUMERIC.get((label or "").lower(), 3)
            return value, label, "taxonomy.tlp_default"

        if key == "default_severity_value":
            # Taxonomy doesn't store a numeric severity itself; surface as
            # missing so use_default kicks in (criterion.default_value = 3
            # for the seeded 'severity' criterion).
            return None, None, "taxonomy.default_severity_value"

        # Generic attribute access — safe with getattr default
        raw = getattr(taxonomy, key or "", None) if key else None
        if raw is None:
            return None, None, f"taxonomy.{key}"
        # If it's already int-like (in scale), reuse; otherwise treat as a label.
        try:
            value = int(raw)
            label = await self._lookup_scale_label(criterion.id, value)
            return value, label, f"taxonomy.{key}"
        except (TypeError, ValueError):
            value = await self._lookup_value_by_label(criterion.id, str(raw))
            return value, str(raw), f"taxonomy.{key}"

    async def _resolve_case_custom_value(
        self, case, criterion: PrioritizationCriterionModel,
    ) -> tuple[int | None, str | None, str]:
        """Lookup case_custom_values.value WHERE service_catalog_fields.field_key = source_field_key."""
        if not criterion.source_field_key:
            return None, None, "no_source_field_key"
        result = await self.db.execute(text(
            "SELECT cv.value FROM case_custom_values cv "
            "JOIN service_catalog_fields f ON f.id = cv.field_id "
            "WHERE cv.case_id = :cid AND f.field_key = :k LIMIT 1"
        ), {"cid": case.id, "k": criterion.source_field_key})
        row = result.first()
        if row is None or row[0] is None:
            return None, None, "no_custom_value"
        raw = row[0]
        try:
            value = int(raw)
        except (TypeError, ValueError):
            return None, None, "non_numeric_custom_value"
        label = await self._lookup_scale_label(criterion.id, value)
        return value, label, f"case.custom_values.{criterion.source_field_key}"

    async def _lookup_scale_label(
        self, criterion_id: str, numeric_value: int,
    ) -> str | None:
        stmt = select(PrioritizationScaleModel.label).where(
            PrioritizationScaleModel.criterion_id == criterion_id,
            PrioritizationScaleModel.numeric_value == numeric_value,
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def _lookup_value_by_label(
        self, criterion_id: str, label: str,
    ) -> int | None:
        stmt = select(PrioritizationScaleModel.numeric_value).where(
            PrioritizationScaleModel.criterion_id == criterion_id,
            PrioritizationScaleModel.label == label,
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()
