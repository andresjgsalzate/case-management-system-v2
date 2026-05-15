"""Tests for Sub-spec 02 — Security Taxonomies module."""
import pytest


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
