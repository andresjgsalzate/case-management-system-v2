"""Tests for Sub-spec 05 — n8n Bridge."""


def test_models_import_smoke():
    """All 3 n8n_bridge models import without errors."""
    from backend.src.modules.n8n_bridge.infrastructure.models import (
        ApprovalRequestModel,
        PlaybookRunCallbackModel,
        PlaybookRunModel,
    )
    assert PlaybookRunModel.__tablename__ == "playbook_runs"
    assert ApprovalRequestModel.__tablename__ == "approval_requests"
    assert PlaybookRunCallbackModel.__tablename__ == "playbook_run_callbacks"
