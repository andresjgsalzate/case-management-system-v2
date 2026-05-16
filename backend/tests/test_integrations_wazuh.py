"""Tests for Sub-spec 04 — Inbound Integrations & Wazuh Adapter."""


def test_models_import_smoke():
    """All 4 integrations models import without errors."""
    from backend.src.modules.integrations.infrastructure.models import (
        InboundEventModel,
        IntegrationMappingModel,
        IntegrationSourceModel,
        WazuhRuleTaxonomyMapModel,
    )
    assert IntegrationSourceModel.__tablename__ == "integration_sources"
    assert IntegrationMappingModel.__tablename__ == "integration_mappings"
    assert InboundEventModel.__tablename__ == "inbound_events"
    assert WazuhRuleTaxonomyMapModel.__tablename__ == "wazuh_rule_to_taxonomy_map"
