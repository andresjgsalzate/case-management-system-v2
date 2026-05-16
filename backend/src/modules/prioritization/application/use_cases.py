"""Prioritization use cases.

This file ships incrementally:
- Task 4: __init__ + _resolve_criterion_value (data_source dispatch).
- Task 5: calculate_priority (happy path).
- Task 6: missing-data strategies (skip / use_default / error).
- Task 7: multi-tenant formula resolution.
- Task 8: create_formula_version.
- Task 10: manual_recalculation + history.
"""
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.src.core.exceptions import (
    BusinessRuleError,
    NotFoundError,
    ValidationError,
)
# Repo doesn't have a dedicated OperationalError — use BusinessRuleError for
# engine-level invariant violations (no formula / no threshold matches).
OperationalError = BusinessRuleError
from backend.src.modules.prioritization.application.derived_handlers import (
    DERIVED_HANDLERS,
    DerivedResult,
)
from backend.src.modules.prioritization.infrastructure.models import (
    CasePriorityCalculationModel,
    PrioritizationCriterionModel,
    PrioritizationFormulaCriterionModel,
    PrioritizationFormulaModel,
    PrioritizationScaleModel,
    PrioritizationThresholdModel,
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

    # ── Engine ──────────────────────────────────────────────────────────

    async def calculate_priority(
        self,
        *,
        case_id: str,
        triggered_by: str = "case_created",
        triggered_by_user: str | None = None,
    ) -> CasePriorityCalculationModel:
        """Compute priority for a case using the active formula + persist audit.

        Task 5 minimal version:
        - Formula resolution = hardcoded 'soc-default' global (Task 7 perfects it
          with taxonomy → tenant → global fallback chain).
        - Missing-data strategy handling: use_default applies criterion.default_value;
          skip drops the criterion WITHOUT renormalizing remaining weights (Task 6
          adds proper renormalization); error raises ValidationError.
        - Updates cases.priority_id atomically with calculation persistence.
        """
        from backend.src.modules.cases.infrastructure.models import CaseModel

        case = await self.db.get(CaseModel, case_id)
        if case is None:
            raise NotFoundError(f"Case {case_id} not found")

        formula = await self._resolve_formula_for_case(case)
        if formula is None:
            raise OperationalError(
                "No active default formula found for tenant or globally"
            )

        # Load formula's criteria with weights
        fc_stmt = (
            select(PrioritizationFormulaCriterionModel, PrioritizationCriterionModel)
            .join(
                PrioritizationCriterionModel,
                PrioritizationCriterionModel.id
                == PrioritizationFormulaCriterionModel.criterion_id,
            )
            .where(PrioritizationFormulaCriterionModel.formula_id == formula.id)
        )
        rows = (await self.db.execute(fc_stmt)).all()

        # Pass 1: resolve every criterion and apply missing-data strategy.
        # Defer weight aggregation to Pass 2 so we can renormalize after any skip.
        inputs: dict[str, dict] = {}
        kept: list[tuple[str, Decimal, int]] = []  # (code, raw_weight, value)
        for fc, criterion in rows:
            value, label, source = await self._resolve_criterion_value(case, criterion)
            entry: dict = {
                "value": value, "label": label,
                "weight": float(fc.weight),
                "source": criterion.data_source,
            }

            if value is None:
                strategy = criterion.missing_data_strategy
                if strategy == "error":
                    raise ValidationError(
                        f"Required criterion '{criterion.code}' has no value"
                    )
                if strategy == "use_default":
                    value = criterion.default_value
                    entry["value"] = value
                    entry["label"] = await self._lookup_scale_label(
                        criterion.id, value,
                    ) if value is not None else None
                    entry["source"] = f"default({source})"
                else:  # 'skip' — drop and renormalize at end
                    entry["skipped"] = True
                    entry["reason"] = source
                    inputs[criterion.code] = entry
                    continue

            inputs[criterion.code] = entry
            kept.append((criterion.code, fc.weight, value))

        if not kept:
            raise ValidationError(
                "Cannot calculate priority — all criteria are missing/skipped"
            )

        # Pass 2: renormalize remaining weights to sum 1.00, then compute weighted_sum.
        total_weight = sum(w for _, w, _ in kept)
        weighted_sum = Decimal("0")
        for code, raw_w, value in kept:
            normalized = raw_w / total_weight
            inputs[code]["weight_normalized"] = float(normalized)
            weighted_sum += Decimal(str(value)) * normalized

        # Find threshold matching weighted_sum
        priority = await self._find_priority_by_threshold(formula.id, weighted_sum)
        if priority is None:
            raise OperationalError(
                f"No threshold matches weighted_sum={weighted_sum} for formula {formula.id}"
            )

        # Persist calculation + update case
        calc = CasePriorityCalculationModel(
            id=str(uuid.uuid4()),
            case_id=case.id,
            formula_id=formula.id,
            formula_version=formula.version,
            inputs=inputs,
            weighted_sum=weighted_sum,
            resulting_priority_id=priority,
            triggered_by=triggered_by,
            triggered_by_user=triggered_by_user,
        )
        self.db.add(calc)
        case.priority_id = priority
        case.updated_at = datetime.now(timezone.utc)
        await self.db.flush()
        return calc

    async def _resolve_formula_for_case(self, case) -> PrioritizationFormulaModel | None:
        """Task 5: hardcoded — pick 'soc-default' global. Task 7 perfects with
        taxonomy.prioritization_formula_id → tenant default → global fallback.
        """
        stmt = (
            select(PrioritizationFormulaModel)
            .where(
                PrioritizationFormulaModel.logical_key == "soc-default",
                PrioritizationFormulaModel.is_active.is_(True),
                PrioritizationFormulaModel.tenant_id.is_(None),
            )
            .limit(1)
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def _find_priority_by_threshold(
        self, formula_id: str, weighted_sum: Decimal,
    ) -> str | None:
        """Returns the priority_id whose threshold range contains weighted_sum.

        Range comparison: min_value <= value <= max_value (inclusive both ends).
        """
        stmt = select(PrioritizationThresholdModel.priority_id).where(
            PrioritizationThresholdModel.formula_id == formula_id,
            PrioritizationThresholdModel.min_value <= weighted_sum,
            PrioritizationThresholdModel.max_value >= weighted_sum,
        ).limit(1)
        return (await self.db.execute(stmt)).scalar_one_or_none()
