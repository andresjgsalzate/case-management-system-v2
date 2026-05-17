"""Forensic module unit tests."""
import pytest


def test_models_import_smoke():
    """All 4 forensic models import without errors."""
    from backend.src.modules.forensic.infrastructure.models import (
        ForensicArtifactModel,
        ForensicHuntModel,
        ForensicHuntResultModel,
        ForensicHuntAttachmentModel,
    )
    assert ForensicArtifactModel.__tablename__ == "forensic_artifacts"
    assert ForensicHuntModel.__tablename__ == "forensic_hunts"
    assert ForensicHuntResultModel.__tablename__ == "forensic_hunt_results"
    assert ForensicHuntAttachmentModel.__tablename__ == "forensic_hunt_attachments"
