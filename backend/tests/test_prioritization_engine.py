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


def test_resolve_taxonomy_field_tlp_default():
    """Criterion with data_source=taxonomy_field, source_field_key=tlp_default → numeric mapping."""
    from sqlalchemy import text

    async def _q(session):
        from backend.src.modules.prioritization.application.use_cases import (
            PrioritizationUseCases,
        )
        from backend.src.modules.prioritization.infrastructure.models import (
            PrioritizationCriterionModel,
        )
        # Use seeded data_sensitivity criterion (taxonomy_field → tlp_default)
        criterion = (await session.execute(
            text(
                "SELECT id, code, data_source, source_field_key, "
                "missing_data_strategy, default_value "
                "FROM prioritization_criteria "
                "WHERE code = 'data_sensitivity' AND tenant_id IS NULL"
            )
        )).first()
        crit_obj = PrioritizationCriterionModel(
            id=criterion[0], code=criterion[1], name="",
            data_source=criterion[2], source_field_key=criterion[3],
            missing_data_strategy=criterion[4], default_value=criterion[5],
        )
        # Use seeded RANSOM-LOCKBIT taxonomy (tlp_default='red')
        tax_row = (await session.execute(text(
            "SELECT id FROM security_taxonomies "
            "WHERE tuic_code = 'RANSOM-LOCKBIT' AND tenant_id IS NULL"
        ))).first()

        class _FakeCase:
            id = "test-case-1"
            tenant_id = "test-tenant"
            taxonomy_id = tax_row[0]

        uc = PrioritizationUseCases(db=session)
        return await uc._resolve_criterion_value(_FakeCase(), crit_obj)

    value, label, source = _run_db_query(_q)
    assert value == 5, f"Expected 5 for TLP red, got {value}"
    assert label == "red"
    assert source == "taxonomy.tlp_default"


def test_resolve_taxonomy_field_returns_none_for_missing_taxonomy():
    """case.taxonomy_id=None → (None, None, 'no_taxonomy')."""
    async def _q(session):
        from backend.src.modules.prioritization.application.use_cases import (
            PrioritizationUseCases,
        )
        from backend.src.modules.prioritization.infrastructure.models import (
            PrioritizationCriterionModel,
        )
        crit_obj = PrioritizationCriterionModel(
            id="x", code="data_sensitivity", name="",
            data_source="taxonomy_field", source_field_key="tlp_default",
            missing_data_strategy="use_default", default_value=3,
        )

        class _FakeCase:
            id = "test-case-2"
            tenant_id = "test-tenant"
            taxonomy_id = None

        uc = PrioritizationUseCases(db=session)
        return await uc._resolve_criterion_value(_FakeCase(), crit_obj)

    value, label, source = _run_db_query(_q)
    assert value is None
    assert label is None
    assert source == "no_taxonomy"


def test_resolve_derived_repetition_count_handler():
    """data_source='derived' → DERIVED_HANDLERS dispatch by source_field_key."""
    async def _q(session):
        from backend.src.modules.prioritization.application.use_cases import (
            PrioritizationUseCases,
        )
        from backend.src.modules.prioritization.infrastructure.models import (
            PrioritizationCriterionModel,
        )
        crit_obj = PrioritizationCriterionModel(
            id="x", code="repetition_count", name="",
            data_source="derived", source_field_key="repetition_count_handler",
            missing_data_strategy="use_default", default_value=1,
        )

        class _FakeCase:
            id = "test-case-3"
            tenant_id = "test-tenant-no-cases"
            taxonomy_id = None  # handler returns "Aislado" when no taxonomy

        uc = PrioritizationUseCases(db=session)
        return await uc._resolve_criterion_value(_FakeCase(), crit_obj)

    value, label, source = _run_db_query(_q)
    assert value == 1
    assert label == "Aislado"
    assert source == "derived.repetition_count_handler"


def test_resolve_derived_unknown_handler_returns_none():
    """data_source='derived' with unregistered source_field_key → (None, None, 'no_handler')."""
    async def _q(session):
        from backend.src.modules.prioritization.application.use_cases import (
            PrioritizationUseCases,
        )
        from backend.src.modules.prioritization.infrastructure.models import (
            PrioritizationCriterionModel,
        )
        crit_obj = PrioritizationCriterionModel(
            id="x", code="custom_derived", name="",
            data_source="derived", source_field_key="nonexistent_handler",
            missing_data_strategy="use_default", default_value=1,
        )

        class _FakeCase:
            id = "x"
            tenant_id = "x"
            taxonomy_id = None

        uc = PrioritizationUseCases(db=session)
        return await uc._resolve_criterion_value(_FakeCase(), crit_obj)

    _value, _label, source = _run_db_query(_q)
    assert source == "no_handler"


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
