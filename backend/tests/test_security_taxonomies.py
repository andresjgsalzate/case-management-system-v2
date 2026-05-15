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
            async with AsyncSession(engine) as session:
                return await async_query(session)
        finally:
            await engine.dispose()

    return asyncio.run(_go())


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
