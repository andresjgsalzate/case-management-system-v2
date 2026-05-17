"""Forensic module unit tests."""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

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


def test_detect_destructive_quarantine():
    from backend.src.modules.forensic.application.catalog_sync import (
        detect_destructive,
    )
    assert detect_destructive("Windows.Remediation.QuarantineHost") is True
    assert detect_destructive("Windows.Detection.Yara.Process") is False


def test_detect_evidence():
    from backend.src.modules.forensic.application.catalog_sync import (
        detect_evidence,
    )
    assert detect_evidence("Windows.Memory.Acquire") is True
    assert detect_evidence("Windows.Forensics.Timeline") is True
    assert detect_evidence("Windows.Detection.Yara.Process") is False


def test_infer_category_collection():
    from backend.src.modules.forensic.application.catalog_sync import (
        infer_category,
    )
    assert infer_category("Windows.Memory.Acquire") == "collection"
    assert infer_category("Windows.Detection.Yara.Process") == "detection"
    assert infer_category("Windows.Remediation.QuarantineHost") == "remediation"


@pytest.mark.asyncio
async def test_list_clients_passes_org_id_to_velo():
    from backend.src.modules.forensic.application.use_cases import (
        ForensicUseCases,
    )
    fake_tenant = MagicMock()
    fake_tenant.id = "t1"
    fake_tenant.velo_org_id = "O.passes_org_id"

    mock_db = AsyncMock()
    mock_db.get = AsyncMock(return_value=fake_tenant)

    with patch(
        "backend.src.modules.forensic.application.use_cases.get_velo_client"
    ) as mock_get:
        mock_velo = MagicMock()
        mock_velo.list_clients = AsyncMock(return_value=[
            {"client_id": "C.x", "hostname": "h1", "os": "Windows",
             "last_seen_at": None},
        ])
        mock_get.return_value = mock_velo

        uc = ForensicUseCases(db=mock_db)
        clients = await uc.list_clients(tenant_id="t1")

    assert len(clients) == 1
    assert clients[0].client_id == "C.x"
    mock_velo.list_clients.assert_called_once_with(
        org_id="O.passes_org_id", label=None, limit=100,
    )


def test_launch_hunt_infer_launched_via_ui_direct():
    from backend.src.modules.forensic.application.use_cases import (
        ForensicUseCases,
    )
    uc = ForensicUseCases(db=AsyncMock())
    actor = MagicMock(user_id="u1")
    assert uc._infer_launched_via(actor, None) == "ui_direct"
    assert uc._infer_launched_via(actor, "n8n-run-x") == "ui_via_n8n"
    assert uc._infer_launched_via(None, "n8n-run-x") == "automation_n8n"


def test_launch_hunt_infer_launched_via_no_launcher_raises():
    from backend.src.core.exceptions import BusinessRuleError
    from backend.src.modules.forensic.application.use_cases import (
        ForensicUseCases,
    )
    uc = ForensicUseCases(db=AsyncMock())
    with pytest.raises(BusinessRuleError):
        uc._infer_launched_via(None, None)


def test_launch_hunt_merge_parameters_applies_defaults():
    from backend.src.modules.forensic.application.use_cases import (
        ForensicUseCases,
    )
    uc = ForensicUseCases(db=AsyncMock())
    schema = [
        {"name": "YaraRules", "default": "rule default {}"},
        {"name": "MaxFileSize", "default": 1048576},
        {"name": "NoDefault"},
    ]
    supplied = {"MaxFileSize": 9999}
    merged = uc._merge_parameters(schema, supplied)
    assert merged["YaraRules"] == "rule default {}"
    assert merged["MaxFileSize"] == 9999
    assert "NoDefault" not in merged


@pytest.mark.asyncio
async def test_destructive_governance_no_n8n_run_denied():
    from backend.src.core.exceptions import PermissionDeniedError
    from backend.src.modules.forensic.application.use_cases import (
        ForensicUseCases,
    )
    artifact = MagicMock(name="Windows.Remediation.Quarantine")
    artifact.name = "Windows.Remediation.Quarantine"
    uc = ForensicUseCases(db=AsyncMock())
    with pytest.raises(PermissionDeniedError, match="must be launched via"):
        await uc._enforce_destructive_governance(
            n8n_run_id=None, approval_request_id="appr-1",
            case_id="c1", artifact=artifact,
        )


@pytest.mark.asyncio
async def test_destructive_governance_no_approval_denied():
    from backend.src.core.exceptions import PermissionDeniedError
    from backend.src.modules.forensic.application.use_cases import (
        ForensicUseCases,
    )
    artifact = MagicMock()
    artifact.name = "Windows.Remediation.Quarantine"
    uc = ForensicUseCases(db=AsyncMock())
    with pytest.raises(PermissionDeniedError, match="approval_request_id"):
        await uc._enforce_destructive_governance(
            n8n_run_id="run-1", approval_request_id=None,
            case_id="c1", artifact=artifact,
        )


@pytest.mark.asyncio
async def test_destructive_governance_approval_not_approved_denied():
    from backend.src.core.exceptions import PermissionDeniedError
    from backend.src.modules.forensic.application.use_cases import (
        ForensicUseCases,
    )
    artifact = MagicMock()
    artifact.name = "Windows.Remediation.Quarantine"

    pending_approval = MagicMock()
    pending_approval.status = "pending"
    pending_approval.case_id = "c1"

    mock_db = AsyncMock()
    mock_db.get = AsyncMock(return_value=pending_approval)

    uc = ForensicUseCases(db=mock_db)
    with pytest.raises(PermissionDeniedError, match="status='pending'"):
        await uc._enforce_destructive_governance(
            n8n_run_id="run-1", approval_request_id="appr-1",
            case_id="c1", artifact=artifact,
        )


@pytest.mark.asyncio
async def test_destructive_governance_approved_for_correct_case_ok():
    from backend.src.modules.forensic.application.use_cases import (
        ForensicUseCases,
    )
    artifact = MagicMock()
    artifact.name = "Windows.Remediation.Quarantine"

    approved = MagicMock()
    approved.status = "approved"
    approved.case_id = "c1"

    mock_db = AsyncMock()
    mock_db.get = AsyncMock(return_value=approved)

    uc = ForensicUseCases(db=mock_db)
    # No exception raised
    await uc._enforce_destructive_governance(
        n8n_run_id="run-1", approval_request_id="appr-1",
        case_id="c1", artifact=artifact,
    )


@pytest.mark.asyncio
async def test_destructive_governance_approval_for_wrong_case_denied():
    from backend.src.core.exceptions import PermissionDeniedError
    from backend.src.modules.forensic.application.use_cases import (
        ForensicUseCases,
    )
    artifact = MagicMock()
    artifact.name = "Windows.Remediation.Quarantine"

    approved = MagicMock()
    approved.status = "approved"
    approved.case_id = "other-case"

    mock_db = AsyncMock()
    mock_db.get = AsyncMock(return_value=approved)

    uc = ForensicUseCases(db=mock_db)
    with pytest.raises(PermissionDeniedError, match="not for case"):
        await uc._enforce_destructive_governance(
            n8n_run_id="run-1", approval_request_id="appr-1",
            case_id="c1", artifact=artifact,
        )


def _make_fake_hunt(*, status: str = "running", launched_by: str = "u1"):
    h = MagicMock()
    h.id = "hunt-1"
    h.status = status
    h.velo_hunt_id = "H.abc"
    h.velo_org_id = "O.test"
    h.launched_by_user_id = launched_by
    h.completed_at = None
    h.error = None
    return h


@pytest.mark.asyncio
async def test_cancel_hunt_invalid_status_raises():
    from backend.src.core.exceptions import ValidationError
    from backend.src.modules.forensic.application.use_cases import (
        ForensicUseCases,
    )
    uc = ForensicUseCases(db=AsyncMock())
    with patch.object(
        uc, "_load_hunt_for_update",
        new=AsyncMock(return_value=_make_fake_hunt(status="completed")),
    ):
        actor = MagicMock(user_id="u1")
        with pytest.raises(ValidationError, match="status='completed'"):
            await uc.cancel_hunt(actor=actor, hunt_id="hunt-1")


@pytest.mark.asyncio
async def test_cancel_hunt_owner_checks_cancel_own_perm():
    from backend.src.modules.forensic.application.use_cases import (
        ForensicUseCases,
    )
    mock_db = AsyncMock()
    uc = ForensicUseCases(db=mock_db)
    hunt = _make_fake_hunt(status="running", launched_by="u1")

    with patch.object(
        uc, "_load_hunt_for_update", new=AsyncMock(return_value=hunt),
    ), patch(
        "backend.src.modules.forensic.application.use_cases.has_permission",
        new=AsyncMock(return_value=True),
    ) as mock_hp, patch(
        "backend.src.modules.forensic.application.use_cases.get_velo_client"
    ) as mock_get_velo:
        mock_get_velo.return_value = MagicMock(cancel_hunt=AsyncMock())
        actor = MagicMock(user_id="u1", role_id="r1")
        result = await uc.cancel_hunt(actor=actor, hunt_id="hunt-1")

    assert result.status == "cancelled"
    mock_hp.assert_called_once()
    assert mock_hp.call_args.args[2:] == ("forensic", "cancel_own")


@pytest.mark.asyncio
async def test_cancel_hunt_non_owner_checks_cancel_any_perm():
    from backend.src.modules.forensic.application.use_cases import (
        ForensicUseCases,
    )
    uc = ForensicUseCases(db=AsyncMock())
    hunt = _make_fake_hunt(status="running", launched_by="other-user")

    with patch.object(
        uc, "_load_hunt_for_update", new=AsyncMock(return_value=hunt),
    ), patch(
        "backend.src.modules.forensic.application.use_cases.has_permission",
        new=AsyncMock(return_value=True),
    ) as mock_hp, patch(
        "backend.src.modules.forensic.application.use_cases.get_velo_client"
    ) as mock_get_velo:
        mock_get_velo.return_value = MagicMock(cancel_hunt=AsyncMock())
        actor = MagicMock(user_id="u1", role_id="r1")
        await uc.cancel_hunt(actor=actor, hunt_id="hunt-1")

    assert mock_hp.call_args.args[2:] == ("forensic", "cancel_any")


@pytest.mark.asyncio
async def test_cancel_hunt_velo_failure_still_marks_cancelled():
    from backend.src.modules.forensic.application.use_cases import (
        ForensicUseCases,
    )
    uc = ForensicUseCases(db=AsyncMock())
    hunt = _make_fake_hunt(status="running", launched_by="u1")

    with patch.object(
        uc, "_load_hunt_for_update", new=AsyncMock(return_value=hunt),
    ), patch(
        "backend.src.modules.forensic.application.use_cases.has_permission",
        new=AsyncMock(return_value=True),
    ), patch(
        "backend.src.modules.forensic.application.use_cases.get_velo_client"
    ) as mock_get_velo:
        mock_velo = MagicMock()
        mock_velo.cancel_hunt = AsyncMock(side_effect=RuntimeError("velo down"))
        mock_get_velo.return_value = mock_velo
        actor = MagicMock(user_id="u1", role_id="r1")
        result = await uc.cancel_hunt(
            actor=actor, hunt_id="hunt-1", reason="cleanup",
        )

    assert result.status == "cancelled"


@pytest.mark.asyncio
async def test_cancel_hunt_records_reason_in_error():
    from backend.src.modules.forensic.application.use_cases import (
        ForensicUseCases,
    )
    uc = ForensicUseCases(db=AsyncMock())
    hunt = _make_fake_hunt(status="running", launched_by="u1")

    with patch.object(
        uc, "_load_hunt_for_update", new=AsyncMock(return_value=hunt),
    ), patch(
        "backend.src.modules.forensic.application.use_cases.has_permission",
        new=AsyncMock(return_value=True),
    ), patch(
        "backend.src.modules.forensic.application.use_cases.get_velo_client"
    ) as mock_get_velo:
        mock_get_velo.return_value = MagicMock(cancel_hunt=AsyncMock())
        actor = MagicMock(user_id="u1", role_id="r1", full_name="Alice")
        result = await uc.cancel_hunt(
            actor=actor, hunt_id="hunt-1", reason="false alarm",
        )

    assert "false alarm" in (result.error or "")
    assert "Alice" in (result.error or "")


@pytest.mark.asyncio
async def test_attach_artifact_missing_velo_hunt_id_raises():
    from backend.src.core.exceptions import ValidationError
    from backend.src.modules.forensic.application.callback_handler import (
        ForensicCallbackHandler,
    )
    handler = ForensicCallbackHandler(db=AsyncMock(), system_user_id="sys")
    case = MagicMock(id="c1", tenant_id="t1")
    run = MagicMock(id="r1")
    with pytest.raises(ValidationError, match="velo_hunt_id"):
        await handler.handle_attach_artifact(
            case=case, run=run, payload={"artifact_name": "X"},
        )


@pytest.mark.asyncio
async def test_attach_artifact_hunt_not_found_raises():
    from backend.src.core.exceptions import NotFoundError
    from backend.src.modules.forensic.application.callback_handler import (
        ForensicCallbackHandler,
    )
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none = MagicMock(return_value=None)
    mock_db.execute = AsyncMock(return_value=mock_result)

    handler = ForensicCallbackHandler(db=mock_db, system_user_id="sys")
    case = MagicMock(id="c1", tenant_id="t1")
    run = MagicMock(id="r1")
    with pytest.raises(NotFoundError, match="not found"):
        await handler.handle_attach_artifact(
            case=case, run=run,
            payload={"velo_hunt_id": "H.missing"},
        )


@pytest.mark.asyncio
async def test_attach_artifact_idempotent_on_completed_hunt():
    from backend.src.modules.forensic.application.callback_handler import (
        ForensicCallbackHandler,
    )
    completed_hunt = MagicMock()
    completed_hunt.status = "completed"
    completed_hunt.id = "hunt-1"

    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none = MagicMock(return_value=completed_hunt)
    mock_db.execute = AsyncMock(return_value=mock_result)

    handler = ForensicCallbackHandler(db=mock_db, system_user_id="sys")
    case = MagicMock(id="c1", tenant_id="t1")
    run = MagicMock(id="r1")
    response = await handler.handle_attach_artifact(
        case=case, run=run,
        payload={"velo_hunt_id": "H.done", "client_results": []},
    )
    assert response["ok"] is True
    assert response["noop"] is True
    assert response["hunt_status"] == "completed"


def _make_timeout_hunt(
    hunt_id: str = "h1", velo_hunt_id: str | None = "H.expired"
):
    h = MagicMock()
    h.id = hunt_id
    h.status = "running"
    h.velo_hunt_id = velo_hunt_id
    h.velo_org_id = "O.test"
    h.completed_at = None
    h.error = None
    return h


@pytest.mark.asyncio
async def test_check_hunt_timeouts_marks_returned_hunts_as_timeout():
    from backend.src.modules.forensic.application.jobs import (
        check_hunt_timeouts_once,
    )
    h1 = _make_timeout_hunt("h1", "H.exp1")
    h2 = _make_timeout_hunt("h2", "H.exp2")

    mock_result = MagicMock()
    mock_result.scalars = MagicMock(
        return_value=MagicMock(all=MagicMock(return_value=[h1, h2]))
    )
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=mock_result)

    mock_velo = MagicMock()
    mock_velo.cancel_hunt = AsyncMock()
    with patch(
        "backend.src.modules.forensic.application.jobs.get_velo_client",
        return_value=mock_velo,
    ):
        n = await check_hunt_timeouts_once(mock_db)

    assert n == 2
    assert h1.status == "timeout"
    assert h2.status == "timeout"
    assert h1.completed_at is not None
    assert h2.completed_at is not None
    assert mock_velo.cancel_hunt.call_count == 2


@pytest.mark.asyncio
async def test_check_hunt_timeouts_velo_failure_still_marks():
    from backend.src.modules.forensic.application.jobs import (
        check_hunt_timeouts_once,
    )
    h = _make_timeout_hunt("h1", "H.exp")

    mock_result = MagicMock()
    mock_result.scalars = MagicMock(
        return_value=MagicMock(all=MagicMock(return_value=[h]))
    )
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=mock_result)

    mock_velo = MagicMock()
    mock_velo.cancel_hunt = AsyncMock(side_effect=RuntimeError("velo down"))
    with patch(
        "backend.src.modules.forensic.application.jobs.get_velo_client",
        return_value=mock_velo,
    ):
        n = await check_hunt_timeouts_once(mock_db)

    assert n == 1
    assert h.status == "timeout"


@pytest.mark.asyncio
async def test_check_hunt_timeouts_skips_velo_when_no_velo_hunt_id():
    """Hunt that never reached Velo (velo_hunt_id is None) → no cancel call."""
    from backend.src.modules.forensic.application.jobs import (
        check_hunt_timeouts_once,
    )
    h = _make_timeout_hunt("h1", velo_hunt_id=None)

    mock_result = MagicMock()
    mock_result.scalars = MagicMock(
        return_value=MagicMock(all=MagicMock(return_value=[h]))
    )
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=mock_result)

    mock_velo = MagicMock()
    mock_velo.cancel_hunt = AsyncMock()
    with patch(
        "backend.src.modules.forensic.application.jobs.get_velo_client",
        return_value=mock_velo,
    ):
        await check_hunt_timeouts_once(mock_db)

    assert h.status == "timeout"
    mock_velo.cancel_hunt.assert_not_called()
