"""Tests for Sub-spec 06 — Operational Center UI backend."""


def test_integration_health_model_smoke():
    """IntegrationHealthModel imports + maps to expected table."""
    from backend.src.modules.operational_center.infrastructure.models import (
        IntegrationHealthModel,
    )
    assert IntegrationHealthModel.__tablename__ == "integration_health"
