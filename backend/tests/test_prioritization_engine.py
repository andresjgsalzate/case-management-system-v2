"""Tests for Sub-spec 03 — Prioritization Engine."""
import pytest


def test_security_taxonomies_prioritization_formula_fk_present():
    """security_taxonomies.prioritization_formula_id declares FK to prioritization_formulas.id (Sub-spec 03 Task 2)."""
    # Pre-import prioritization models so the FK resolves
    from backend.src.modules.prioritization.infrastructure import models as _prio  # noqa: F401
    from backend.src.modules.security_taxonomies.infrastructure.models import (
        SecurityTaxonomyModel,
    )
    col = SecurityTaxonomyModel.__table__.c.prioritization_formula_id
    fks = list(col.foreign_keys)
    assert len(fks) == 1, (
        f"Expected exactly 1 FK on prioritization_formula_id, got {len(fks)}"
    )
    fk = fks[0]
    assert fk.column.table.name == "prioritization_formulas", (
        f"FK target table '{fk.column.table.name}', expected 'prioritization_formulas'"
    )
    assert fk.column.name == "id"
    assert fk.ondelete == "SET NULL"


def test_models_import_smoke():
    """All 6 prioritization models import without errors."""
    from backend.src.modules.prioritization.infrastructure.models import (
        PrioritizationCriterionModel,
        PrioritizationScaleModel,
        PrioritizationFormulaModel,
        PrioritizationFormulaCriterionModel,
        PrioritizationThresholdModel,
        CasePriorityCalculationModel,
    )
    assert PrioritizationCriterionModel.__tablename__ == "prioritization_criteria"
    assert PrioritizationScaleModel.__tablename__ == "prioritization_scales"
    assert PrioritizationFormulaModel.__tablename__ == "prioritization_formulas"
    assert PrioritizationFormulaCriterionModel.__tablename__ == "prioritization_formula_criteria"
    assert PrioritizationThresholdModel.__tablename__ == "prioritization_thresholds"
    assert CasePriorityCalculationModel.__tablename__ == "case_priority_calculations"
