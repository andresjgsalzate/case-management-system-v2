"""Tests for Sub-spec 02 — Security Taxonomies module."""
import pytest


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
