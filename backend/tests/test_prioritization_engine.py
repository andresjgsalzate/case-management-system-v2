"""Tests for Sub-spec 03 — Prioritization Engine."""
import pytest


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
