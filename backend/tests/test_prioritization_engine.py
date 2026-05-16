"""Tests for Sub-spec 03 — Prioritization Engine."""
import asyncio
import pytest


def _run_db_query(async_query):
    """Run async DB query inline against the real DB (mirrors security_taxonomies tests)."""
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from dotenv import dotenv_values

    env = dotenv_values("backend/.env")
    real_url = env.get("DATABASE_URL")
    if not real_url:
        pytest.skip("DATABASE_URL not in backend/.env")

    async def _go():
        engine = create_async_engine(real_url)
        try:
            async with AsyncSession(engine, expire_on_commit=False) as session:
                return await async_query(session)
        finally:
            await engine.dispose()

    return asyncio.run(_go())


def test_prioritization_permissions_seeded():
    """6 prioritization permissions present across the 5 existing roles."""
    from sqlalchemy import text

    expected_actions = {
        "read", "manage_criteria", "manage_formulas",
        "manage_global", "recalculate", "read_calculations",
    }

    async def _q(session):
        result = await session.execute(text(
            "SELECT DISTINCT action FROM permissions WHERE module = 'prioritization'"
        ))
        return {row[0] for row in result.all()}

    actions = _run_db_query(_q)
    missing = expected_actions - actions
    assert not missing, f"Missing actions: {missing}"


def test_prioritization_criteria_seeded():
    """6 global criteria from spec §4.1 seeded with correct data_source."""
    from sqlalchemy import text

    expected = {
        "severity": "taxonomy_field",
        "impact": "case_custom_value",
        "asset_criticality": "asset_field",
        "data_sensitivity": "taxonomy_field",
        "user_visibility": "case_custom_value",
        "repetition_count": "derived",
    }

    async def _q(session):
        result = await session.execute(text(
            "SELECT code, data_source FROM prioritization_criteria "
            "WHERE tenant_id IS NULL"
        ))
        return {row[0]: row[1] for row in result.all()}

    actual = _run_db_query(_q)
    for code, source in expected.items():
        assert code in actual, f"Missing criterion: {code}"
        assert actual[code] == source, (
            f"Criterion '{code}' data_source = '{actual[code]}', expected '{source}'"
        )


def test_prioritization_formulas_seeded():
    """3 global formulas active per logical_key with weights summing to 1.00."""
    from sqlalchemy import text

    async def _q(session):
        # Verify the 3 formulas exist as v1, active, with their criteria sums
        result = await session.execute(text(
            "SELECT f.logical_key, f.version, f.is_active, SUM(fc.weight) "
            "FROM prioritization_formulas f "
            "JOIN prioritization_formula_criteria fc ON fc.formula_id = f.id "
            "WHERE f.tenant_id IS NULL "
            "GROUP BY f.logical_key, f.version, f.is_active "
            "ORDER BY f.logical_key"
        ))
        return [(row[0], row[1], row[2], float(row[3])) for row in result.all()]

    rows = _run_db_query(_q)
    by_key = {key: (version, active, total) for key, version, active, total in rows}

    assert "soc-default" in by_key
    assert "compliance-focused" in by_key
    assert "user-impact-focused" in by_key

    for key, (version, active, total) in by_key.items():
        assert version == 1, f"{key} version is {version}, expected 1"
        assert active is True, f"{key} should be active"
        assert abs(total - 1.0) < 0.001, (
            f"{key} weights sum to {total}, expected 1.00"
        )


def test_prioritization_thresholds_seeded():
    """Each formula has thresholds linked to existing case_priorities."""
    from sqlalchemy import text

    async def _q(session):
        result = await session.execute(text(
            "SELECT f.logical_key, COUNT(t.id) FROM prioritization_formulas f "
            "JOIN prioritization_thresholds t ON t.formula_id = f.id "
            "WHERE f.tenant_id IS NULL "
            "GROUP BY f.logical_key"
        ))
        return {row[0]: row[1] for row in result.all()}

    counts = _run_db_query(_q)
    assert counts.get("soc-default", 0) >= 4
    assert counts.get("compliance-focused", 0) >= 4
    assert counts.get("user-impact-focused", 0) >= 4


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
