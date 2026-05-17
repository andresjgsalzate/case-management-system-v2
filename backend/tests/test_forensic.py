"""Forensic module unit tests."""
import asyncio

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


def _get_real_url():
    from dotenv import dotenv_values
    env = dotenv_values("backend/.env")
    url = env.get("DATABASE_URL")
    if not url:
        pytest.skip("DATABASE_URL not in backend/.env")
    return url


def test_forensic_permissions_seeded():
    """7 forensic actions present in permissions table after migrations."""
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    async def _check():
        engine = create_async_engine(_get_real_url())
        try:
            async with engine.connect() as conn:
                rows = (await conn.execute(text(
                    "SELECT DISTINCT action FROM permissions WHERE module = 'forensic'"
                ))).fetchall()
                return {r[0] for r in rows}
        finally:
            await engine.dispose()

    actions = asyncio.run(_check())
    expected = {
        "read", "launch_ro", "launch_evidence",
        "cancel_own", "cancel_any",
        "sync_catalog", "manage_featured",
    }
    assert actions == expected, (
        f"Missing: {expected - actions}, Extra: {actions - expected}"
    )
