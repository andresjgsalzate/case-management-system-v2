"""Tests for Sub-spec 02 — Security Taxonomies module."""
import asyncio
import pytest


def _run_db_query(async_query):
    """Run an async DB query inline using a fresh session/event loop.

    Tests in this repo run against a sandbox conftest that overrides DATABASE_URL
    to a fake host, so AsyncSessionLocal can't be used in unit tests. This helper
    constructs an engine bound to the REAL DATABASE_URL from .env so seed-state
    tests can verify migrations actually applied.
    """
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


class _FakeActor:
    """Minimal CurrentUser-like stub for use case tests."""
    def __init__(self, user_id, role_name, tenant_id="t-fake"):
        from sqlalchemy import text as _text
        self.user_id = user_id
        self.tenant_id = tenant_id
        self.role_name = role_name
        # role_id resolved at first access via DB
        self._role_id: str | None = None


async def _actor_role_id(session, actor):
    if actor._role_id is None:
        from sqlalchemy import text
        row = (await session.execute(text(
            "SELECT id FROM roles WHERE name = :name AND tenant_id IS NULL LIMIT 1"
        ), {"name": actor.role_name})).first()
        actor._role_id = row[0] if row else None
    return actor._role_id


def _build_admin_actor():
    """Returns a fake actor bound to Super Admin user/role."""
    actor = _FakeActor(user_id="ec35a91e-5778-4210-a631-c5ed673c679d", role_name="Super Admin")
    return actor


def _build_manager_actor():
    """Manager role: has create/update but NOT manage_global, NOT delete."""
    actor = _FakeActor(user_id="ec35a91e-5778-4210-a631-c5ed673c679d", role_name="Manager")
    return actor


def test_create_taxonomy_global_emits_audit():
    """Platform admin creates global taxonomy → row + audit log entry."""
    import uuid
    from sqlalchemy import text

    tuic = f"TEST-CREATE-{uuid.uuid4().hex[:8].upper()}"

    async def _run(session):
        from backend.src.modules.security_taxonomies.application.use_cases import (
            SecurityTaxonomyUseCases,
        )
        from backend.src.modules.security_taxonomies.application.dtos import (
            TaxonomyCreatePayload,
        )
        actor = _build_admin_actor()
        actor._role_id = await _actor_role_id(session, actor)
        uc = SecurityTaxonomyUseCases(db=session)
        payload = TaxonomyCreatePayload(
            tenant_id=None, tuic_code=tuic, name="Test create",
            default_case_type="event", requires_ticket=False, triage_mode="auto",
            tlp_default="amber", mitre_techniques=[],
        )
        tax = await uc.create_taxonomy(actor=actor, payload=payload)
        await session.commit()
        # Verify audit row
        audit = (await session.execute(text(
            "SELECT change_type FROM security_taxonomies_audit_log "
            "WHERE taxonomy_id = :id"
        ), {"id": tax.id})).first()
        return tax.id, tax.tenant_id, tax.tuic_code, (audit[0] if audit else None)

    async def _cleanup(session):
        await session.execute(text(
            "DELETE FROM security_taxonomies WHERE tuic_code = :code AND tenant_id IS NULL"
        ), {"code": tuic})
        await session.commit()

    try:
        tax_id, tenant_id, code, audit_type = _run_db_query(_run)
        assert tenant_id is None
        assert code == tuic
        assert audit_type == "created"
    finally:
        _run_db_query(_cleanup)


def test_create_global_denied_without_manage_global():
    """Manager role cannot create global taxonomies."""
    from backend.src.core.exceptions import PermissionDeniedError

    async def _run(session):
        from backend.src.modules.security_taxonomies.application.use_cases import (
            SecurityTaxonomyUseCases,
        )
        from backend.src.modules.security_taxonomies.application.dtos import (
            TaxonomyCreatePayload,
        )
        actor = _build_manager_actor()
        actor._role_id = await _actor_role_id(session, actor)
        uc = SecurityTaxonomyUseCases(db=session)
        payload = TaxonomyCreatePayload(
            tenant_id=None, tuic_code="MANAGER-CANT-DO-THIS",
            name="x", default_case_type="event",
        )
        try:
            await uc.create_taxonomy(actor=actor, payload=payload)
            return False  # should have raised
        except PermissionDeniedError:
            return True

    assert _run_db_query(_run) is True


def test_tuic_code_unique_per_tenant():
    """Two globals with same tuic_code → second raises ValidationError."""
    import uuid
    from sqlalchemy import text
    from backend.src.core.exceptions import ValidationError

    tuic = f"TEST-DUP-{uuid.uuid4().hex[:8].upper()}"

    async def _create_first(session):
        from backend.src.modules.security_taxonomies.application.use_cases import (
            SecurityTaxonomyUseCases,
        )
        from backend.src.modules.security_taxonomies.application.dtos import (
            TaxonomyCreatePayload,
        )
        actor = _build_admin_actor()
        actor._role_id = await _actor_role_id(session, actor)
        uc = SecurityTaxonomyUseCases(db=session)
        await uc.create_taxonomy(
            actor=actor,
            payload=TaxonomyCreatePayload(tenant_id=None, tuic_code=tuic, name="dup"),
        )
        await session.commit()

    async def _create_dup(session):
        from backend.src.modules.security_taxonomies.application.use_cases import (
            SecurityTaxonomyUseCases,
        )
        from backend.src.modules.security_taxonomies.application.dtos import (
            TaxonomyCreatePayload,
        )
        actor = _build_admin_actor()
        actor._role_id = await _actor_role_id(session, actor)
        uc = SecurityTaxonomyUseCases(db=session)
        try:
            await uc.create_taxonomy(
                actor=actor,
                payload=TaxonomyCreatePayload(tenant_id=None, tuic_code=tuic, name="dup2"),
            )
            return False
        except ValidationError:
            return True

    async def _cleanup(session):
        await session.execute(text(
            "DELETE FROM security_taxonomies WHERE tuic_code = :code AND tenant_id IS NULL"
        ), {"code": tuic})
        await session.commit()

    try:
        _run_db_query(_create_first)
        assert _run_db_query(_create_dup) is True
    finally:
        _run_db_query(_cleanup)


def test_update_creates_audit_log_entry():
    """Updating a field writes a diff row to audit log."""
    import uuid
    from sqlalchemy import text

    tuic = f"TEST-UPD-{uuid.uuid4().hex[:8].upper()}"

    async def _setup(session):
        from backend.src.modules.security_taxonomies.application.use_cases import (
            SecurityTaxonomyUseCases,
        )
        from backend.src.modules.security_taxonomies.application.dtos import (
            TaxonomyCreatePayload,
        )
        actor = _build_admin_actor()
        actor._role_id = await _actor_role_id(session, actor)
        uc = SecurityTaxonomyUseCases(db=session)
        tax = await uc.create_taxonomy(
            actor=actor,
            payload=TaxonomyCreatePayload(tenant_id=None, tuic_code=tuic, name="before"),
        )
        await session.commit()
        return tax.id

    async def _update(session, tax_id):
        from backend.src.modules.security_taxonomies.application.use_cases import (
            SecurityTaxonomyUseCases,
        )
        from backend.src.modules.security_taxonomies.application.dtos import (
            TaxonomyUpdatePayload,
        )
        actor = _build_admin_actor()
        actor._role_id = await _actor_role_id(session, actor)
        uc = SecurityTaxonomyUseCases(db=session)
        await uc.update_taxonomy(
            actor=actor, taxonomy_id=tax_id,
            updates=TaxonomyUpdatePayload(name="after"),
        )
        await session.commit()
        audits = (await session.execute(text(
            "SELECT change_type, field_changes FROM security_taxonomies_audit_log "
            "WHERE taxonomy_id = :id ORDER BY changed_at ASC"
        ), {"id": tax_id})).all()
        return [(r[0], r[1]) for r in audits]

    async def _cleanup(session):
        await session.execute(text(
            "DELETE FROM security_taxonomies WHERE tuic_code = :code AND tenant_id IS NULL"
        ), {"code": tuic})
        await session.commit()

    try:
        tax_id = _run_db_query(_setup)
        audits = _run_db_query(lambda s: _update(s, tax_id))
        types = [t for (t, _) in audits]
        assert "created" in types
        assert "updated" in types
        # Diff for update should record name change
        update_diff = next(c for (t, c) in audits if t == "updated")
        assert "name" in update_diff
        assert update_diff["name"]["from"] == "before"
        assert update_diff["name"]["to"] == "after"
    finally:
        _run_db_query(_cleanup)


def test_update_no_changes_skips_audit():
    """Update with same values → no new audit row."""
    import uuid
    from sqlalchemy import text

    tuic = f"TEST-NOOP-{uuid.uuid4().hex[:8].upper()}"

    async def _setup(session):
        from backend.src.modules.security_taxonomies.application.use_cases import (
            SecurityTaxonomyUseCases,
        )
        from backend.src.modules.security_taxonomies.application.dtos import (
            TaxonomyCreatePayload,
        )
        actor = _build_admin_actor()
        actor._role_id = await _actor_role_id(session, actor)
        uc = SecurityTaxonomyUseCases(db=session)
        tax = await uc.create_taxonomy(
            actor=actor,
            payload=TaxonomyCreatePayload(tenant_id=None, tuic_code=tuic, name="same"),
        )
        await session.commit()
        return tax.id

    async def _noop(session, tax_id):
        from backend.src.modules.security_taxonomies.application.use_cases import (
            SecurityTaxonomyUseCases,
        )
        from backend.src.modules.security_taxonomies.application.dtos import (
            TaxonomyUpdatePayload,
        )
        actor = _build_admin_actor()
        actor._role_id = await _actor_role_id(session, actor)
        uc = SecurityTaxonomyUseCases(db=session)
        await uc.update_taxonomy(
            actor=actor, taxonomy_id=tax_id,
            updates=TaxonomyUpdatePayload(name="same"),
        )
        await session.commit()
        count = (await session.execute(text(
            "SELECT COUNT(*) FROM security_taxonomies_audit_log "
            "WHERE taxonomy_id = :id"
        ), {"id": tax_id})).scalar()
        return count

    async def _cleanup(session):
        await session.execute(text(
            "DELETE FROM security_taxonomies WHERE tuic_code = :code AND tenant_id IS NULL"
        ), {"code": tuic})
        await session.commit()

    try:
        tax_id = _run_db_query(_setup)
        count = _run_db_query(lambda s: _noop(s, tax_id))
        assert count == 1, f"Expected 1 audit row (created only), got {count}"
    finally:
        _run_db_query(_cleanup)


def test_soft_delete_reason_required():
    """soft_delete without reason → ValidationError."""
    import uuid
    from sqlalchemy import text
    from backend.src.core.exceptions import ValidationError

    tuic = f"TEST-DEL-{uuid.uuid4().hex[:8].upper()}"

    async def _setup(session):
        from backend.src.modules.security_taxonomies.application.use_cases import (
            SecurityTaxonomyUseCases,
        )
        from backend.src.modules.security_taxonomies.application.dtos import (
            TaxonomyCreatePayload,
        )
        actor = _build_admin_actor()
        actor._role_id = await _actor_role_id(session, actor)
        uc = SecurityTaxonomyUseCases(db=session)
        tax = await uc.create_taxonomy(
            actor=actor,
            payload=TaxonomyCreatePayload(tenant_id=None, tuic_code=tuic, name="to-delete"),
        )
        await session.commit()
        return tax.id

    async def _try_delete(session, tax_id):
        from backend.src.modules.security_taxonomies.application.use_cases import (
            SecurityTaxonomyUseCases,
        )
        actor = _build_admin_actor()
        actor._role_id = await _actor_role_id(session, actor)
        uc = SecurityTaxonomyUseCases(db=session)
        try:
            await uc.soft_delete(actor=actor, taxonomy_id=tax_id, reason="")
            return False
        except ValidationError:
            return True

    async def _cleanup(session):
        await session.execute(text(
            "DELETE FROM security_taxonomies WHERE tuic_code = :code AND tenant_id IS NULL"
        ), {"code": tuic})
        await session.commit()

    try:
        tax_id = _run_db_query(_setup)
        assert _run_db_query(lambda s: _try_delete(s, tax_id)) is True
    finally:
        _run_db_query(_cleanup)


def test_soft_delete_with_active_descendants_rejected():
    """Cannot soft-delete parent if active children exist."""
    import uuid
    from sqlalchemy import text
    from backend.src.core.exceptions import ValidationError

    parent_code = f"TEST-PARENT-{uuid.uuid4().hex[:8].upper()}"
    child_code = f"TEST-CHILD-{uuid.uuid4().hex[:8].upper()}"
    parent_id_holder: dict[str, str] = {}

    async def _setup(session):
        from backend.src.modules.security_taxonomies.application.use_cases import (
            SecurityTaxonomyUseCases,
        )
        from backend.src.modules.security_taxonomies.application.dtos import (
            TaxonomyCreatePayload,
        )
        actor = _build_admin_actor()
        actor._role_id = await _actor_role_id(session, actor)
        uc = SecurityTaxonomyUseCases(db=session)
        parent = await uc.create_taxonomy(
            actor=actor,
            payload=TaxonomyCreatePayload(tenant_id=None, tuic_code=parent_code, name="parent"),
        )
        await session.commit()
        child = await uc.create_taxonomy(
            actor=actor,
            payload=TaxonomyCreatePayload(
                tenant_id=None, tuic_code=child_code, name="child", parent_id=parent.id,
            ),
        )
        await session.commit()
        parent_id_holder["id"] = parent.id

    async def _try_delete(session):
        from backend.src.modules.security_taxonomies.application.use_cases import (
            SecurityTaxonomyUseCases,
        )
        actor = _build_admin_actor()
        actor._role_id = await _actor_role_id(session, actor)
        uc = SecurityTaxonomyUseCases(db=session)
        try:
            await uc.soft_delete(actor=actor, taxonomy_id=parent_id_holder["id"], reason="test")
            return False
        except ValidationError:
            return True

    async def _cleanup(session):
        await session.execute(text(
            "DELETE FROM security_taxonomies WHERE tuic_code IN (:p, :c) AND tenant_id IS NULL"
        ), {"p": parent_code, "c": child_code})
        await session.commit()

    try:
        _run_db_query(_setup)
        assert _run_db_query(_try_delete) is True
    finally:
        _run_db_query(_cleanup)


def test_get_taxonomy_fallback_to_global():
    """get_taxonomy(tuic_code, tenant_id) returns global when no tenant override exists."""
    async def _q(session):
        from backend.src.modules.security_taxonomies.application.use_cases import (
            SecurityTaxonomyUseCases,
        )
        uc = SecurityTaxonomyUseCases(db=session)
        tax = await uc.get_taxonomy(tuic_code="RANSOM-LOCKBIT", tenant_id="any-tenant-id-no-override")
        return (tax.tuic_code if tax else None, tax.tenant_id if tax else None)

    code, tenant_id = _run_db_query(_q)
    assert code == "RANSOM-LOCKBIT"
    assert tenant_id is None, f"Expected global (tenant_id=None), got {tenant_id}"


def test_get_taxonomy_with_override_wins():
    """When a tenant-specific override exists, it overrides the global."""
    import uuid
    from sqlalchemy import text

    tenant = "test-tenant-override-1"
    override_id = str(uuid.uuid4())

    async def _setup(session):
        # Need a created_by user
        user_row = (await session.execute(text(
            "SELECT u.id FROM users u JOIN roles r ON r.id = u.role_id "
            "WHERE r.name IN ('Super Admin', 'Admin') AND r.tenant_id IS NULL LIMIT 1"
        ))).first()
        assert user_row, "no admin user available"
        user_id = user_row[0]
        await session.execute(text(
            "INSERT INTO security_taxonomies "
            "(id, tenant_id, tuic_code, name, default_case_type, requires_ticket, "
            " triage_mode, triage_timeout_seconds, tlp_default, mitre_techniques, "
            " is_active, created_at, updated_at, created_by) "
            "VALUES (:id, :tenant, 'RANSOM-LOCKBIT', 'Tenant Override', 'incident', "
            "        true, 'auto', 300, 'red', CAST('[]' AS json), true, NOW(), NOW(), :uid)"
        ), {"id": override_id, "tenant": tenant, "uid": user_id})
        await session.commit()

    async def _lookup(session):
        from backend.src.modules.security_taxonomies.application.use_cases import (
            SecurityTaxonomyUseCases,
        )
        uc = SecurityTaxonomyUseCases(db=session)
        tax = await uc.get_taxonomy(tuic_code="RANSOM-LOCKBIT", tenant_id=tenant)
        return (tax.tenant_id, tax.name) if tax else (None, None)

    async def _cleanup(session):
        await session.execute(text(
            "DELETE FROM security_taxonomies WHERE id = :id"
        ), {"id": override_id})
        await session.commit()

    try:
        _run_db_query(_setup)
        tenant_id, name = _run_db_query(_lookup)
        assert tenant_id == tenant, f"Expected tenant override, got tenant_id={tenant_id}"
        assert name == "Tenant Override", f"Expected override name, got '{name}'"
    finally:
        _run_db_query(_cleanup)


def test_get_taxonomy_returns_none_when_no_match():
    """No tenant override AND no global → returns None."""
    async def _q(session):
        from backend.src.modules.security_taxonomies.application.use_cases import (
            SecurityTaxonomyUseCases,
        )
        uc = SecurityTaxonomyUseCases(db=session)
        return await uc.get_taxonomy(tuic_code="NONEXISTENT-CODE-XYZ", tenant_id="any-tenant")

    result = _run_db_query(_q)
    assert result is None


def test_list_taxonomies_returns_globals_for_tenant_without_overrides():
    """list_taxonomies(tenant_id=X with no overrides) returns globals."""
    async def _q(session):
        from backend.src.modules.security_taxonomies.application.use_cases import (
            SecurityTaxonomyUseCases,
        )
        uc = SecurityTaxonomyUseCases(db=session)
        taxonomies = await uc.list_taxonomies(tenant_id="tenant-with-no-overrides-xyz")
        return [t.tuic_code for t in taxonomies]

    codes = _run_db_query(_q)
    # Should include at least the well-known globals seeded in Task 6
    assert "RANSOM-LOCKBIT" in codes
    assert "PHISH-MAIL" in codes
    assert len(codes) >= 30


def test_global_taxonomies_seeded_with_hierarchy():
    """≥30 global taxonomies + RANSOM-LOCKBIT has RANSOMWARE as parent (Sub-spec 02 Task 6)."""
    from sqlalchemy import text

    async def _count(session):
        result = await session.execute(text(
            "SELECT COUNT(*) FROM security_taxonomies WHERE tenant_id IS NULL"
        ))
        return result.scalar()

    async def _lockbit_parent(session):
        result = await session.execute(text(
            "SELECT p.tuic_code FROM security_taxonomies c "
            "JOIN security_taxonomies p ON p.id = c.parent_id "
            "WHERE c.tuic_code = 'RANSOM-LOCKBIT' AND c.tenant_id IS NULL"
        ))
        row = result.first()
        return row[0] if row else None

    count = _run_db_query(_count)
    assert count >= 30, f"Expected ≥30 global taxonomies, got {count}"

    parent_code = _run_db_query(_lockbit_parent)
    assert parent_code == "RANSOMWARE", (
        f"RANSOM-LOCKBIT parent expected 'RANSOMWARE', got '{parent_code}'"
    )


def test_soc_teams_seeded():
    """16 SOC teams from spec §4.1 are present as globals with correct attributes."""
    from sqlalchemy import text

    expected = {
        # name → (team_category, is_notification_only)
        "Incidentes - SOC":          ("operational",       False),
        "Soporte IT":                ("operational",       False),
        "Customer Success":          ("operational",       True),
        "Infraestructura":           ("technical_support", False),
        "Bases de datos":            ("technical_support", False),
        "Aplicaciones":              ("technical_support", False),
        "Adm. Antivirus":            ("technical_support", False),
        "Adm. Correo":               ("technical_support", False),
        "Net&Sec":                   ("technical_support", False),
        "Ethical Hacker":            ("technical_support", False),
        "Segu Info. - Risk":         ("governance",        False),
        "Recursos Humanos":          ("governance",        True),
        "Datos Personales":          ("governance",        True),
        "Legal":                     ("legal",             True),
        "Director de Producto":      ("executive",         True),
        "Director Arquitectura":     ("executive",         True),
        "Alta Dirección":            ("executive",         True),
    }
    # Spec §4.1 has 17 entries (3 operational + 7 technical + 3 governance + 1 legal + 3 executive)

    async def _q(session):
        result = await session.execute(text(
            "SELECT name, team_category, is_notification_only FROM teams "
            "WHERE tenant_id IS NULL AND name = ANY(:names)"
        ).bindparams(names=list(expected.keys())))
        return {row[0]: (row[1], row[2]) for row in result.all()}

    actual = _run_db_query(_q)
    missing = set(expected) - set(actual)
    assert not missing, f"Missing teams: {missing}"
    for name, (cat, notif_only) in expected.items():
        assert actual[name] == (cat, notif_only), (
            f"Team '{name}': expected ({cat}, {notif_only}), got {actual[name]}"
        )


def test_security_taxonomies_permissions_seeded():
    """8 security_taxonomies permissions assigned to expected roles (Sub-spec 02 Task 4)."""
    from sqlalchemy import text

    expected_actions = {
        "read", "create", "update", "delete",
        "manage_global", "read_audit_log", "export", "import",
    }

    async def _q(session):
        result = await session.execute(text(
            "SELECT DISTINCT action FROM permissions WHERE module = 'security_taxonomies'"
        ))
        return {row[0] for row in result.all()}

    actions = _run_db_query(_q)
    missing = expected_actions - actions
    assert not missing, f"Missing actions: {missing}"


def test_security_taxonomies_role_assignments():
    """Each role gets the right subset of security_taxonomies permissions."""
    from sqlalchemy import text

    expected = {
        "Super Admin": {"read", "create", "update", "delete",
                        "manage_global", "read_audit_log", "export", "import"},
        "Admin":       {"read", "create", "update", "delete",
                        "read_audit_log", "export", "import"},
        "Manager":     {"read", "create", "update", "read_audit_log", "export"},
        "Agent":       {"read", "read_audit_log"},
        "Reporter":    {"read"},
    }

    async def _q(session):
        result = await session.execute(text(
            "SELECT r.name, p.action "
            "FROM permissions p JOIN roles r ON r.id = p.role_id "
            "WHERE p.module = 'security_taxonomies' AND r.tenant_id IS NULL"
        ))
        out: dict[str, set[str]] = {}
        for role_name, action in result.all():
            out.setdefault(role_name, set()).add(action)
        return out

    actual = _run_db_query(_q)
    for role_name, exp_actions in expected.items():
        got = actual.get(role_name, set())
        assert got == exp_actions, (
            f"Role '{role_name}': expected {exp_actions}, got {got}"
        )


def test_cases_taxonomy_id_has_fk_to_security_taxonomies():
    """cases.taxonomy_id declares FK to security_taxonomies.id (Sub-spec 02 Task 3)."""
    # Pre-import security_taxonomies models so the FK on cases.taxonomy_id resolves
    # (main.py does not yet import this module — no router shipped in Task 3).
    from backend.src.modules.security_taxonomies.infrastructure import models as _stx  # noqa: F401
    from backend.src.modules.cases.infrastructure.models import CaseModel
    col = CaseModel.__table__.c.taxonomy_id
    fks = list(col.foreign_keys)
    assert len(fks) == 1, f"Expected exactly 1 FK on cases.taxonomy_id, got {len(fks)}"
    fk = fks[0]
    assert fk.column.table.name == "security_taxonomies", (
        f"FK target table is '{fk.column.table.name}', expected 'security_taxonomies'"
    )
    assert fk.column.name == "id", f"FK target column is '{fk.column.name}', expected 'id'"
    assert fk.ondelete == "SET NULL", f"FK ondelete is '{fk.ondelete}', expected 'SET NULL'"


def test_team_has_category_and_notification_only_columns():
    """TeamModel exposes team_category and is_notification_only (Sub-spec 02 Task 2)."""
    from backend.src.modules.teams.infrastructure.models import TeamModel
    cols = {c.name for c in TeamModel.__table__.columns}
    assert "team_category" in cols, "team_category column missing"
    assert "is_notification_only" in cols, "is_notification_only column missing"


def test_models_import_smoke():
    """All 4 security_taxonomies models import without errors."""
    from backend.src.modules.security_taxonomies.infrastructure.models import (
        SecurityTaxonomyModel,
        SecurityTaxonomyAuditLogModel,
        TaxonomyNotificationModel,
        TaxonomyCatalogMappingModel,
    )
    assert SecurityTaxonomyModel.__tablename__ == "security_taxonomies"
    assert SecurityTaxonomyAuditLogModel.__tablename__ == "security_taxonomies_audit_log"
    assert TaxonomyNotificationModel.__tablename__ == "taxonomy_notifications"
    assert TaxonomyCatalogMappingModel.__tablename__ == "taxonomy_catalog_mappings"
