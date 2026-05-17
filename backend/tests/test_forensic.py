"""Forensic module unit tests."""
import asyncio
from unittest.mock import AsyncMock, patch

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


@pytest.mark.asyncio
async def test_velo_client_list_artifacts_passes_org_id():
    from backend.src.modules.forensic.infrastructure.velo_client import (
        VelociraptorClient,
    )
    client = VelociraptorClient(
        endpoint="grpc://velo.local:8001",
        api_config_path="/tmp/api.config.yaml",
    )
    with patch.object(client, "_query_vql", new=AsyncMock(return_value=[
        {"name": "Windows.Detection.Yara.Process", "type": "CLIENT",
         "description": "x", "parameters": []}
    ])) as mock_q:
        artifacts = await client.list_artifacts(org_id="O.test")
    assert len(artifacts) == 1
    call_kwargs = mock_q.call_args.kwargs
    assert call_kwargs.get("org_id") == "O.test"


@pytest.mark.asyncio
async def test_velo_client_create_hunt_returns_hunt_id():
    from backend.src.modules.forensic.infrastructure.velo_client import (
        VelociraptorClient,
    )
    client = VelociraptorClient(
        endpoint="grpc://velo.local:8001",
        api_config_path="/tmp/api.config.yaml",
    )
    with patch.object(client, "_query_vql", new=AsyncMock(return_value=[
        {"hunt_id": "H.abc123"}
    ])):
        hunt_id = await client.create_hunt(
            org_id="O.test",
            artifact_name="Windows.Detection.Yara.Process",
            parameters={"YaraRules": "rule x { ... }"},
            client_ids=["C.host1"],
        )
    assert hunt_id == "H.abc123"


@pytest.mark.asyncio
async def test_velo_client_health_check_returns_metrics():
    from backend.src.modules.forensic.infrastructure.velo_client import (
        VelociraptorClient,
    )
    client = VelociraptorClient(
        endpoint="grpc://velo.local:8001",
        api_config_path="/tmp/api.config.yaml",
    )
    with patch.object(client, "_query_vql", new=AsyncMock(side_effect=[
        [{"online": 142, "total": 150}],
        [{"active_hunts": 1}],
        [{"version": {"version": "0.74.1"}}],
    ])):
        h = await client.health_check()
    assert h["online_clients"] == 142
    assert h["total_clients"] == 150
    assert h["active_hunts"] == 1
    assert h["version"] == "0.74.1"


def test_sha256_canonical_deterministic():
    from backend.src.modules.forensic.application.hash_utils import (
        sha256_canonical,
    )
    a = sha256_canonical({"b": 1, "a": 2})
    b = sha256_canonical({"a": 2, "b": 1})
    assert a == b


def test_sha256_canonical_different_for_different_data():
    from backend.src.modules.forensic.application.hash_utils import (
        sha256_canonical,
    )
    assert sha256_canonical({"x": 1}) != sha256_canonical({"x": 2})


def test_sha256_canonical_returns_64_hex_chars():
    from backend.src.modules.forensic.application.hash_utils import (
        sha256_canonical,
    )
    h = sha256_canonical({"a": 1})
    assert len(h) == 64
    int(h, 16)
