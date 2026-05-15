"""Tests for Sub-spec 02 — Security Taxonomies module."""
import pytest


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
