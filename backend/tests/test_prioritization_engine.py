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


def _compute_with_inputs(values_by_code: dict[str, int | None], weights: dict[str, float]):
    """Helper for missing-strategy unit tests: simulate a formula evaluation
    using PrioritizationUseCases' internal weighted_sum logic.

    Returns (weighted_sum, skipped_codes, kept_codes_with_normalized_weights).
    """
    from decimal import Decimal

    kept: list[tuple[str, Decimal, int]] = []
    skipped: list[str] = []
    for code, value in values_by_code.items():
        if value is None:
            skipped.append(code)
            continue
        kept.append((code, Decimal(str(weights[code])), value))

    if not kept:
        return None, skipped, []

    total_weight = sum(w for _, w, _ in kept)
    normalized = [(c, w / total_weight, v) for c, w, v in kept]
    weighted_sum = sum(Decimal(v) * w for _, w, v in normalized)
    return weighted_sum, skipped, normalized


def test_skip_strategy_renormalizes_remaining_weights():
    """When asset_criticality (weight=0.2) is skipped, severity (0.5) and impact (0.3)
    renormalize to 0.625 and 0.375 — so 5 * 0.625 + 3 * 0.375 = 4.25, not 5*0.5+3*0.3=3.4."""
    from decimal import Decimal

    weighted_sum, skipped, normalized = _compute_with_inputs(
        values_by_code={"severity": 5, "impact": 3, "asset_criticality": None},
        weights={"severity": 0.5, "impact": 0.3, "asset_criticality": 0.2},
    )
    assert skipped == ["asset_criticality"]
    # Normalized weights should sum to 1
    total = sum(w for _, w, _ in normalized)
    assert abs(float(total) - 1.0) < 0.001, f"normalized total = {total}"
    # weighted_sum: 5*(0.5/0.8) + 3*(0.3/0.8) = 3.125 + 1.125 = 4.25
    assert abs(float(weighted_sum) - 4.25) < 0.01, f"got {weighted_sum}"


def test_all_skipped_returns_none():
    """When every criterion is skipped, helper returns None (caller raises)."""
    weighted_sum, skipped, kept = _compute_with_inputs(
        values_by_code={"a": None, "b": None},
        weights={"a": 0.5, "b": 0.5},
    )
    assert weighted_sum is None
    assert set(skipped) == {"a", "b"}
    assert kept == []


def _make_test_case(session, *, case_number_suffix: str, taxonomy_tuic: str | None = None):
    """Helper: insert a minimal case row + return its id.

    Returns (case_id, taxonomy_id_or_none). Caller is responsible for cleanup
    via the case_number prefix matching the cleanup query.
    """
    import uuid as _uuid
    from sqlalchemy import text

    async def _do():
        # Look up bootstrapping foreign keys
        admin_row = (await session.execute(text(
            "SELECT u.id FROM users u JOIN roles r ON r.id = u.role_id "
            "WHERE r.name IN ('Super Admin', 'Admin') AND r.tenant_id IS NULL "
            "ORDER BY u.created_at ASC LIMIT 1"
        ))).first()
        status_row = (await session.execute(text(
            "SELECT id FROM case_statuses WHERE is_final = false LIMIT 1"
        ))).first()
        priority_row = (await session.execute(text(
            "SELECT id FROM case_priorities WHERE name = 'Baja' LIMIT 1"
        ))).first()
        tax_id = None
        if taxonomy_tuic:
            tax_row = (await session.execute(text(
                "SELECT id FROM security_taxonomies "
                "WHERE tuic_code = :c AND tenant_id IS NULL LIMIT 1"
            ), {"c": taxonomy_tuic})).first()
            tax_id = tax_row[0] if tax_row else None

        case_id = str(_uuid.uuid4())
        case_number = f"TEST-PRIO-{case_number_suffix}"
        await session.execute(text(
            "INSERT INTO cases "
            "(id, case_number, title, status_id, priority_id, case_type, "
            " complexity, current_level, taxonomy_id, tenant_id, created_by, "
            " is_archived, created_at, updated_at) "
            "VALUES (:id, :num, 'priority test', :sid, :pid, 'incident', "
            "        'simple', 1, :tid, NULL, :uid, false, NOW(), NOW())"
        ), {
            "id": case_id, "num": case_number,
            "sid": status_row[0], "pid": priority_row[0],
            "tid": tax_id, "uid": admin_row[0],
        })
        await session.commit()
        return case_id, tax_id

    return _do


def test_calculate_priority_persists_calculation_and_updates_case():
    """calculate_priority creates an audit row and updates case.priority_id."""
    import uuid as _uuid
    from sqlalchemy import text

    suffix = _uuid.uuid4().hex[:8].upper()

    async def _setup(session):
        make = _make_test_case(session, case_number_suffix=suffix,
                               taxonomy_tuic="RANSOM-LOCKBIT")
        return await make()

    async def _calculate(session, case_id):
        from backend.src.modules.prioritization.application.use_cases import (
            PrioritizationUseCases,
        )
        uc = PrioritizationUseCases(db=session)
        calc = await uc.calculate_priority(
            case_id=case_id, triggered_by="manual_recalculation",
        )
        await session.commit()
        # Re-read case to confirm priority was updated
        new_pri = (await session.execute(text(
            "SELECT priority_id FROM cases WHERE id = :cid"
        ), {"cid": case_id})).scalar()
        return calc.id, calc.case_id, calc.formula_id, calc.triggered_by, \
               calc.weighted_sum, calc.resulting_priority_id, new_pri, \
               dict(calc.inputs)

    async def _cleanup(session):
        await session.execute(text(
            "DELETE FROM case_priority_calculations "
            "WHERE case_id IN (SELECT id FROM cases WHERE case_number = :n)"
        ), {"n": f"TEST-PRIO-{suffix}"})
        await session.execute(text(
            "DELETE FROM cases WHERE case_number = :n"
        ), {"n": f"TEST-PRIO-{suffix}"})
        await session.commit()

    try:
        case_id, _tax = _run_db_query(_setup)
        calc_id, calc_case, formula_id, triggered_by, weighted, resulting, \
            new_pri, inputs = _run_db_query(lambda s: _calculate(s, case_id))
        assert calc_case == case_id
        assert triggered_by == "manual_recalculation"
        assert formula_id is not None, "Formula should be resolved"
        assert resulting is not None, "Resulting priority should be set"
        assert new_pri == resulting, "case.priority_id should equal resulting_priority_id"
        # weighted_sum should be a positive Decimal (>0 since at least one criterion resolves)
        assert float(weighted) > 0, f"weighted_sum={weighted}, expected > 0"
        # inputs should contain the criteria the formula references
        # (soc-default uses severity, impact, asset_criticality)
        assert "severity" in inputs or "impact" in inputs, (
            f"Expected criteria in inputs, got keys: {list(inputs.keys())}"
        )
    finally:
        _run_db_query(_cleanup)


def test_process_taxonomy_update_skips_non_priority_fields():
    """When changed_fields don't intersect PRIORITY_AFFECTING — returns 0, no recalc."""
    async def _run(session):
        from backend.src.modules.prioritization.application.recalculation_handlers import (
            process_taxonomy_update,
        )
        n = await process_taxonomy_update(
            session,
            taxonomy_id="any-uuid-ignored",
            changed_fields={"name", "description", "mitre_techniques"},
        )
        return n

    assert _run_db_query(_run) == 0


def test_process_taxonomy_update_recalcs_open_cases():
    """Changing prioritization_formula_id triggers recalc for open cases linked."""
    import uuid as _uuid
    from sqlalchemy import text

    suffix = _uuid.uuid4().hex[:8].upper()

    async def _setup(session):
        # Reuse seeded RANSOM-LOCKBIT global taxonomy + create 1 open case linked
        make = _make_test_case(session, case_number_suffix=suffix,
                               taxonomy_tuic="RANSOM-LOCKBIT")
        case_id, tax_id = await make()
        return case_id, tax_id

    async def _trigger(session, taxonomy_id):
        from backend.src.modules.prioritization.application.recalculation_handlers import (
            process_taxonomy_update,
        )
        n = await process_taxonomy_update(
            session,
            taxonomy_id=taxonomy_id,
            changed_fields={"prioritization_formula_id"},
        )
        await session.commit()
        # Confirm calculation row inserted with triggered_by='taxonomy_changed'
        calc_row = (await session.execute(text(
            "SELECT triggered_by FROM case_priority_calculations "
            "WHERE case_id IN (SELECT id FROM cases WHERE case_number = :n) "
            "ORDER BY calculated_at DESC LIMIT 1"
        ), {"n": f"TEST-PRIO-{suffix}"})).scalar()
        return n, calc_row

    async def _cleanup(session):
        await session.execute(text(
            "DELETE FROM case_priority_calculations "
            "WHERE case_id IN (SELECT id FROM cases WHERE case_number = :n)"
        ), {"n": f"TEST-PRIO-{suffix}"})
        await session.execute(text(
            "DELETE FROM cases WHERE case_number = :n"
        ), {"n": f"TEST-PRIO-{suffix}"})
        await session.commit()

    try:
        case_id, tax_id = _run_db_query(_setup)
        n, triggered_by = _run_db_query(lambda s: _trigger(s, tax_id))
        assert n == 1, f"Expected 1 case recalculated, got {n}"
        assert triggered_by == "taxonomy_changed"
    finally:
        _run_db_query(_cleanup)


class _FakeActor:
    """Minimal CurrentUser-like stub for use case tests."""
    def __init__(self, user_id, role_name="Super Admin", tenant_id="t-fake"):
        self.user_id = user_id
        self.tenant_id = tenant_id
        self.role_name = role_name
        self.role_id: str | None = None


async def _resolve_actor_role_id(session, actor: "_FakeActor"):
    if actor.role_id is None:
        from sqlalchemy import text
        row = (await session.execute(text(
            "SELECT id FROM roles WHERE name = :n AND tenant_id IS NULL LIMIT 1"
        ), {"n": actor.role_name})).first()
        actor.role_id = row[0] if row else None
    return actor.role_id


def test_create_formula_v2_supersedes_v1():
    """Creating v2 with base_version_id=v1 → v1.is_active=false, v1.superseded_by_id=v2.id."""
    import uuid as _uuid
    from decimal import Decimal
    from sqlalchemy import text

    logical = f"test-formula-{_uuid.uuid4().hex[:6]}"

    async def _seed_v1(session):
        from backend.src.modules.prioritization.application.use_cases import (
            PrioritizationUseCases,
        )
        actor = _FakeActor(user_id="ec35a91e-5778-4210-a631-c5ed673c679d")
        actor.role_id = await _resolve_actor_role_id(session, actor)
        uc = PrioritizationUseCases(db=session)
        v1 = await uc.create_formula_version(
            actor=actor,
            tenant_id=None,
            logical_key=logical,
            base_version_id=None,
            name="Test v1",
            description="initial",
            criteria_weights={"severity": Decimal("0.5"),
                              "impact": Decimal("0.3"),
                              "asset_criticality": Decimal("0.2")},
            thresholds=[
                (Decimal("0.0"), Decimal("2.49"), "Baja"),
                (Decimal("2.5"), Decimal("3.49"), "Media"),
                (Decimal("3.5"), Decimal("4.49"), "Alta"),
                (Decimal("4.5"), Decimal("5.0"), "Critica"),
            ],
        )
        await session.commit()
        return v1.id

    async def _seed_v2_and_check(session, v1_id):
        from backend.src.modules.prioritization.application.use_cases import (
            PrioritizationUseCases,
        )
        actor = _FakeActor(user_id="ec35a91e-5778-4210-a631-c5ed673c679d")
        actor.role_id = await _resolve_actor_role_id(session, actor)
        uc = PrioritizationUseCases(db=session)
        v2 = await uc.create_formula_version(
            actor=actor,
            tenant_id=None,
            logical_key=logical,
            base_version_id=v1_id,
            name="Test v2",
            description="updated",
            criteria_weights={"severity": Decimal("0.4"),
                              "impact": Decimal("0.4"),
                              "asset_criticality": Decimal("0.2")},
            thresholds=[
                (Decimal("0.0"), Decimal("2.49"), "Baja"),
                (Decimal("2.5"), Decimal("3.49"), "Media"),
                (Decimal("3.5"), Decimal("4.49"), "Alta"),
                (Decimal("4.5"), Decimal("5.0"), "Critica"),
            ],
        )
        await session.commit()
        rows = (await session.execute(text(
            "SELECT version, is_active, superseded_by_id FROM prioritization_formulas "
            "WHERE id IN (:v1, :v2) ORDER BY version"
        ), {"v1": v1_id, "v2": v2.id})).all()
        return v2.id, [(int(r[0]), r[1], r[2]) for r in rows]

    async def _cleanup(session):
        await session.execute(text(
            "DELETE FROM prioritization_formulas "
            "WHERE logical_key = :k AND tenant_id IS NULL"
        ), {"k": logical})
        await session.commit()

    try:
        v1_id = _run_db_query(_seed_v1)
        v2_id, rows = _run_db_query(lambda s: _seed_v2_and_check(s, v1_id))
        # rows ordered by version ASC: [(1, ..., ...), (2, ..., ...)]
        v1_row, v2_row = rows
        assert v1_row[0] == 1 and v2_row[0] == 2
        assert v1_row[1] is False, "v1 should be deactivated after supersession"
        assert v1_row[2] == v2_id, f"v1.superseded_by_id expected {v2_id}, got {v1_row[2]}"
        assert v2_row[1] is True, "v2 should be active"
        assert v2_row[2] is None, "v2 should not be superseded"
    finally:
        _run_db_query(_cleanup)


def test_create_formula_rejects_weights_not_summing_to_one():
    """Weights summing to 0.99 → ValidationError, no row inserted."""
    from decimal import Decimal
    from backend.src.core.exceptions import ValidationError

    async def _run(session):
        from backend.src.modules.prioritization.application.use_cases import (
            PrioritizationUseCases,
        )
        actor = _FakeActor(user_id="ec35a91e-5778-4210-a631-c5ed673c679d")
        actor.role_id = await _resolve_actor_role_id(session, actor)
        uc = PrioritizationUseCases(db=session)
        try:
            await uc.create_formula_version(
                actor=actor, tenant_id=None, logical_key="test-bad-weights",
                base_version_id=None, name="bad", description=None,
                criteria_weights={"severity": Decimal("0.50"),
                                  "impact": Decimal("0.49")},
                thresholds=[(Decimal("0.0"), Decimal("5.0"), "Baja")],
            )
            return False
        except ValidationError:
            return True

    assert _run_db_query(_run) is True


def test_create_formula_rejects_thresholds_with_gap():
    """Thresholds [(0,2),(3,5)] → ValidationError (gap at 2.0–3.0)."""
    from decimal import Decimal
    from backend.src.core.exceptions import ValidationError

    async def _run(session):
        from backend.src.modules.prioritization.application.use_cases import (
            PrioritizationUseCases,
        )
        actor = _FakeActor(user_id="ec35a91e-5778-4210-a631-c5ed673c679d")
        actor.role_id = await _resolve_actor_role_id(session, actor)
        uc = PrioritizationUseCases(db=session)
        try:
            await uc.create_formula_version(
                actor=actor, tenant_id=None, logical_key="test-bad-thresholds",
                base_version_id=None, name="bad", description=None,
                criteria_weights={"severity": Decimal("1.0")},
                thresholds=[
                    (Decimal("0.0"), Decimal("2.0"), "Baja"),
                    (Decimal("3.0"), Decimal("5.0"), "Alta"),  # gap at 2..3
                ],
            )
            return False
        except ValidationError:
            return True

    assert _run_db_query(_run) is True


def test_formula_resolution_via_taxonomy_wins_over_default():
    """When case.taxonomy.prioritization_formula_id is set, that formula is used
    instead of the tenant/global 'soc-default'."""
    import uuid as _uuid
    from sqlalchemy import text

    suffix = _uuid.uuid4().hex[:8].upper()

    async def _setup(session):
        # Point RANSOM-LOCKBIT taxonomy at the compliance-focused formula
        tax_row = (await session.execute(text(
            "SELECT id FROM security_taxonomies "
            "WHERE tuic_code = 'RANSOM-LOCKBIT' AND tenant_id IS NULL"
        ))).first()
        compliance_row = (await session.execute(text(
            "SELECT id FROM prioritization_formulas "
            "WHERE logical_key = 'compliance-focused' AND tenant_id IS NULL "
            "AND is_active = true"
        ))).first()
        original_formula_id = (await session.execute(text(
            "SELECT prioritization_formula_id FROM security_taxonomies WHERE id = :id"
        ), {"id": tax_row[0]})).scalar()
        await session.execute(text(
            "UPDATE security_taxonomies SET prioritization_formula_id = :fid "
            "WHERE id = :tid"
        ), {"fid": compliance_row[0], "tid": tax_row[0]})
        await session.commit()
        # Create case using that taxonomy
        make = _make_test_case(session, case_number_suffix=suffix,
                               taxonomy_tuic="RANSOM-LOCKBIT")
        case_id, _ = await make()
        return case_id, compliance_row[0], tax_row[0], original_formula_id

    async def _calc(session, case_id):
        from backend.src.modules.prioritization.application.use_cases import (
            PrioritizationUseCases,
        )
        uc = PrioritizationUseCases(db=session)
        calc = await uc.calculate_priority(
            case_id=case_id, triggered_by="manual_recalculation",
        )
        await session.commit()
        return calc.formula_id

    async def _cleanup(session, tax_id, original_formula_id):
        await session.execute(text(
            "DELETE FROM case_priority_calculations "
            "WHERE case_id IN (SELECT id FROM cases WHERE case_number = :n)"
        ), {"n": f"TEST-PRIO-{suffix}"})
        await session.execute(text(
            "DELETE FROM cases WHERE case_number = :n"
        ), {"n": f"TEST-PRIO-{suffix}"})
        await session.execute(text(
            "UPDATE security_taxonomies SET prioritization_formula_id = :fid "
            "WHERE id = :tid"
        ), {"fid": original_formula_id, "tid": tax_id})
        await session.commit()

    case_id, expected_formula_id, tax_id, original_formula_id = _run_db_query(_setup)
    try:
        used_formula_id = _run_db_query(lambda s: _calc(s, case_id))
        assert used_formula_id == expected_formula_id, (
            f"Expected compliance-focused {expected_formula_id}, "
            f"engine picked {used_formula_id}"
        )
    finally:
        _run_db_query(lambda s: _cleanup(s, tax_id, original_formula_id))


def test_calculate_priority_renormalizes_when_criterion_skipped():
    """soc-default has 3 criteria; asset_criticality always skips (no asset).
    With renormalize, severity (default=3) and impact (default=3) carry full
    weight: 3*(0.5/0.8) + 3*(0.3/0.8) = 3.0 — NOT 3*0.5+3*0.3=2.4."""
    import uuid as _uuid
    from sqlalchemy import text

    suffix = _uuid.uuid4().hex[:8].upper()

    async def _setup(session):
        make = _make_test_case(session, case_number_suffix=suffix,
                               taxonomy_tuic="RANSOM-LOCKBIT")
        return await make()

    async def _calc(session, case_id):
        from backend.src.modules.prioritization.application.use_cases import (
            PrioritizationUseCases,
        )
        uc = PrioritizationUseCases(db=session)
        calc = await uc.calculate_priority(
            case_id=case_id, triggered_by="manual_recalculation",
        )
        await session.commit()
        return float(calc.weighted_sum), dict(calc.inputs)

    async def _cleanup(session):
        await session.execute(text(
            "DELETE FROM case_priority_calculations "
            "WHERE case_id IN (SELECT id FROM cases WHERE case_number = :n)"
        ), {"n": f"TEST-PRIO-{suffix}"})
        await session.execute(text(
            "DELETE FROM cases WHERE case_number = :n"
        ), {"n": f"TEST-PRIO-{suffix}"})
        await session.commit()

    try:
        case_id, _tax = _run_db_query(_setup)
        weighted, inputs = _run_db_query(lambda s: _calc(s, case_id))
        # Without renormalize: 1.5 + 0.9 = 2.4 (asset dropped silently)
        # With renormalize:    3.0 (severity+impact carry full normalized weight)
        assert abs(weighted - 3.0) < 0.05, (
            f"Expected ~3.0 (renormalized), got {weighted}. "
            f"Likely skip is dropping without renormalize."
        )
        # asset_criticality should be marked skipped
        assert inputs.get("asset_criticality", {}).get("skipped") is True, (
            f"asset_criticality should be skipped, got {inputs.get('asset_criticality')}"
        )
        # severity & impact should have weight_normalized field populated
        assert "weight_normalized" in inputs.get("severity", {}), (
            "severity should have weight_normalized after Task 6"
        )
    finally:
        _run_db_query(_cleanup)


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
