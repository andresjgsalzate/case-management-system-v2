"""Tests for Sub-spec 05 — n8n Bridge."""
import asyncio

import pytest


def _run_db_query(async_query):
    """Run an async DB callable using the real DATABASE_URL (mirrors Spec 04 helper)."""
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from dotenv import dotenv_values

    env = dotenv_values("backend/.env")
    real_url = env.get("DATABASE_URL")
    if not real_url:
        pytest.skip("DATABASE_URL not in backend/.env")

    async def _go():
        engine = create_async_engine(real_url)
        try:
            async with AsyncSession(engine, expire_on_commit=False) as session:
                return await async_query(session)
        finally:
            await engine.dispose()

    return asyncio.run(_go())


def test_n8n_bridge_permissions_seeded():
    """Migration 538c6aad7c8f inserted 5 (module, action) pairs across
    n8n_bridge + approvals."""
    from sqlalchemy import text as _t

    async def _go(session):
        rows = (await session.execute(_t(
            "SELECT DISTINCT module, action FROM permissions "
            "WHERE module IN ('n8n_bridge', 'approvals')"
        ))).all()
        return {(r[0], r[1]) for r in rows}

    pairs = _run_db_query(_go)
    assert pairs == {
        ("n8n_bridge", "trigger_workflow"),
        ("n8n_bridge", "read_runs"),
        ("n8n_bridge", "cancel_run"),
        ("approvals", "approve"),
        ("approvals", "read"),
    }, f"Unexpected seeded pairs: {pairs}"


# ── Task 3: JWT helper for callback auth ───────────────────────────────


def test_callback_jwt_issue_and_validate_roundtrip():
    from backend.src.modules.n8n_bridge.application.jwt_helper import (
        issue_callback_jwt,
        validate_callback_jwt,
    )
    token = issue_callback_jwt(case_id="case-1", ttl_seconds=3600)
    claims = validate_callback_jwt(token, expected_case_id="case-1")
    assert claims["case_id"] == "case-1"
    assert claims["sub"] == "n8n"


def test_callback_jwt_case_id_mismatch_rejected():
    from backend.src.core.exceptions import UnauthorizedError
    from backend.src.modules.n8n_bridge.application.jwt_helper import (
        issue_callback_jwt,
        validate_callback_jwt,
    )
    token = issue_callback_jwt(case_id="case-A", ttl_seconds=3600)
    with pytest.raises(UnauthorizedError):
        validate_callback_jwt(token, expected_case_id="case-B")


def test_callback_jwt_validation_skips_check_when_no_expected_case_id():
    """Validation without expected_case_id returns claims for inspection (used by
    callback dispatch when case_id comes from URL path)."""
    from backend.src.modules.n8n_bridge.application.jwt_helper import (
        issue_callback_jwt,
        validate_callback_jwt,
    )
    token = issue_callback_jwt(case_id="case-X", ttl_seconds=3600)
    claims = validate_callback_jwt(token, expected_case_id=None)
    assert claims["case_id"] == "case-X"


def test_callback_jwt_expired_rejected():
    """Token issued with ttl=-1s is already expired → UnauthorizedError."""
    from backend.src.core.exceptions import UnauthorizedError
    from backend.src.modules.n8n_bridge.application.jwt_helper import (
        issue_callback_jwt,
        validate_callback_jwt,
    )
    token = issue_callback_jwt(case_id="case-1", ttl_seconds=-1)
    with pytest.raises(UnauthorizedError):
        validate_callback_jwt(token, expected_case_id="case-1")


def test_callback_jwt_garbage_token_rejected():
    from backend.src.core.exceptions import UnauthorizedError
    from backend.src.modules.n8n_bridge.application.jwt_helper import (
        validate_callback_jwt,
    )
    with pytest.raises(UnauthorizedError):
        validate_callback_jwt("not.a.jwt", expected_case_id=None)


# ── Task 4: trigger_workflow (CMS → n8n) ───────────────────────────────


import json as _json  # noqa: E402
import os  # noqa: E402

# JWT secret falls back to SECRET_KEY which is already set by conftest.

ADMIN_USER_ID = "ec35a91e-5778-4210-a631-c5ed673c679d"

# Match Sub-spec 04 fixture so source crypto works in DB-touching tests.
os.environ.setdefault(
    "INTEGRATIONS_ENCRYPTION_KEY",
    "Uf0yMQkQS7qc_AQVDGFYNc8Lc4E4l0QYtVkk4IZ5tXU=",
)


async def _seed_n8n_source(session, tenant_id, secret):
    """Insert an integration_sources row of type='n8n' for trigger_workflow."""
    import uuid as _uuid
    from sqlalchemy import text as _t
    from backend.src.modules.integrations.application.crypto import encrypt_secret
    source_id = str(_uuid.uuid4())
    await session.execute(_t(
        "INSERT INTO integration_sources "
        "(id, tenant_id, name, source_type, auth_method, auth_secret_encrypted, "
        "auth_header_name, is_active, total_events_received, "
        "total_events_failed, created_at, updated_at, created_by) "
        "VALUES (:id, :tid, :n, 'n8n', 'hmac', :secret, 'X-CMS-Signature', "
        "true, 0, 0, NOW(), NOW(), :cb)"
    ), {
        "id": source_id, "tid": tenant_id,
        "n": f"n8n-test-{source_id[:8]}",
        "secret": encrypt_secret(secret),
        "cb": ADMIN_USER_ID,
    })
    await session.commit()
    return source_id


async def _seed_minimal_case(session, tenant_id):
    """Create a minimal case for trigger_workflow to act on. Returns case_id."""
    import uuid as _uuid
    from sqlalchemy import text as _t
    # Prerequisites
    svc_id = (await session.execute(_t(
        "SELECT id FROM service_catalog_items LIMIT 1"
    ))).first()[0]
    pri_id = (await session.execute(_t(
        "SELECT id FROM case_priorities LIMIT 1"
    ))).first()[0]
    status_id = (await session.execute(_t(
        "SELECT id FROM case_statuses WHERE slug = 'logged' LIMIT 1"
    ))).first()[0]
    for prefix in ("EVT",):
        exists = (await session.execute(_t(
            "SELECT 1 FROM case_number_ranges "
            "WHERE tenant_id = :t AND prefix = :p LIMIT 1"
        ), {"t": tenant_id, "p": prefix})).first()
        if not exists:
            await session.execute(_t(
                "INSERT INTO case_number_ranges "
                "(id, tenant_id, prefix, range_start, range_end, "
                "current_number, created_at) "
                "VALUES (:id, :t, :p, 1, 999999, 0, NOW())"
            ), {"id": str(_uuid.uuid4()), "t": tenant_id, "p": prefix})
    await session.commit()

    case_id = str(_uuid.uuid4())
    await session.execute(_t(
        "INSERT INTO cases "
        "(id, tenant_id, case_number, title, status_id, priority_id, "
        "complexity, current_level, service_item_id, created_by, "
        "is_archived, case_type, created_at, updated_at) "
        "VALUES (:id, :tid, :cn, 'Trigger test', :sid, :pid, 'simple', 1, "
        ":svc, :cb, false, 'event', NOW(), NOW())"
    ), {
        "id": case_id, "tid": tenant_id,
        "cn": f"EVT-2099-{_uuid.uuid4().hex[:6]}",
        "sid": status_id, "pid": pri_id, "svc": svc_id, "cb": ADMIN_USER_ID,
    })
    await session.commit()
    return case_id


async def _cleanup_n8n_tenant(session, tenant_id):
    from sqlalchemy import text as _t
    for tbl in ("playbook_run_callbacks", "approval_requests",
                "playbook_runs", "cases", "integration_sources",
                "case_number_ranges"):
        await session.execute(_t(
            f"DELETE FROM {tbl} WHERE "
            f"{'playbook_run_id' if tbl == 'playbook_run_callbacks' else 'tenant_id'} "
            f"{'IN (SELECT id FROM playbook_runs WHERE tenant_id = :t)' if tbl == 'playbook_run_callbacks' else '= :t'}"
        ), {"t": tenant_id})
    await session.commit()


def test_trigger_workflow_creates_playbook_run_on_success():
    """Successful 200 response from n8n → playbook_runs row with status='triggered'."""
    import asyncio as _aio
    from unittest.mock import AsyncMock, MagicMock, patch
    import uuid as _uuid
    from sqlalchemy import text as _t
    from backend.src.modules.n8n_bridge.application.use_cases import (
        N8nBridgeUseCases,
    )

    tenant_id = f"t-trig-ok-{_uuid.uuid4().hex[:8]}"
    secret = "trigger-test-secret"

    async def _go():
        from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
        from dotenv import dotenv_values
        env = dotenv_values("backend/.env")
        engine = create_async_engine(env["DATABASE_URL"])
        try:
            async with AsyncSession(engine, expire_on_commit=False) as session:
                await _seed_n8n_source(session, tenant_id, secret)
                case_id = await _seed_minimal_case(session, tenant_id)

                # Stub httpx.AsyncClient so the test doesn't hit a real n8n
                fake_response = MagicMock()
                fake_response.status_code = 200
                fake_response.content = b'{"executionId": "exec-abc"}'
                fake_response.json = MagicMock(
                    return_value={"executionId": "exec-abc"},
                )
                fake_response.raise_for_status = MagicMock(return_value=None)
                fake_client = MagicMock()
                fake_client.__aenter__ = AsyncMock(return_value=fake_client)
                fake_client.__aexit__ = AsyncMock(return_value=None)
                fake_client.post = AsyncMock(return_value=fake_response)

                with patch("httpx.AsyncClient", return_value=fake_client):
                    uc = N8nBridgeUseCases(
                        db=session, cms_base_url="https://cms.test",
                    )
                    run = await uc.trigger_workflow(
                        case_id=case_id,
                        workflow_url="https://n8n.test/webhook/wf-1",
                        triggered_by="manual",
                        triggered_by_user=ADMIN_USER_ID,
                    )
                    # Verify the POST was signed and JWT-bearing
                    assert fake_client.post.await_count == 1
                    call = fake_client.post.await_args
                    headers = call.kwargs.get("headers") or call.args[2]
                    assert headers["X-CMS-Signature"].startswith("sha256=")
                    assert headers["X-CMS-Playbook-Run-Id"] == run.id

                    row = (await session.execute(_t(
                        "SELECT status, triggered_by, n8n_execution_id, "
                        "workflow_url FROM playbook_runs WHERE id = :id"
                    ), {"id": run.id})).first()
                    await _cleanup_n8n_tenant(session, tenant_id)
                    return row
        finally:
            await engine.dispose()

    row = _aio.run(_go())
    assert row[0] == "triggered"
    assert row[1] == "manual"
    assert row[2] == "exec-abc"
    assert row[3] == "https://n8n.test/webhook/wf-1"


def test_trigger_workflow_signs_body_with_hmac():
    """Verify the X-CMS-Signature header matches HMAC-SHA256 of the request body."""
    import asyncio as _aio
    import hashlib
    import hmac as _hmac
    import uuid as _uuid
    from unittest.mock import AsyncMock, MagicMock, patch
    from backend.src.modules.n8n_bridge.application.use_cases import (
        N8nBridgeUseCases,
    )

    tenant_id = f"t-trig-hmac-{_uuid.uuid4().hex[:8]}"
    secret = "hmac-roundtrip-secret"

    async def _go():
        from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
        from dotenv import dotenv_values
        env = dotenv_values("backend/.env")
        engine = create_async_engine(env["DATABASE_URL"])
        try:
            async with AsyncSession(engine, expire_on_commit=False) as session:
                await _seed_n8n_source(session, tenant_id, secret)
                case_id = await _seed_minimal_case(session, tenant_id)

                captured = {}

                async def _capturing_post(url, **kwargs):
                    captured["body"] = kwargs.get("content")
                    captured["headers"] = kwargs.get("headers")
                    resp = MagicMock()
                    resp.status_code = 200
                    resp.content = b"{}"
                    resp.json = MagicMock(return_value={})
                    resp.raise_for_status = MagicMock(return_value=None)
                    return resp

                fake_client = MagicMock()
                fake_client.__aenter__ = AsyncMock(return_value=fake_client)
                fake_client.__aexit__ = AsyncMock(return_value=None)
                fake_client.post = AsyncMock(side_effect=_capturing_post)

                with patch("httpx.AsyncClient", return_value=fake_client):
                    uc = N8nBridgeUseCases(
                        db=session, cms_base_url="https://cms.test",
                    )
                    await uc.trigger_workflow(
                        case_id=case_id,
                        workflow_url="https://n8n.test/webhook/wf-sig",
                    )
                await _cleanup_n8n_tenant(session, tenant_id)
                return captured, secret
        finally:
            await engine.dispose()

    captured, sec = _aio.run(_go())
    expected = _hmac.new(
        sec.encode(), captured["body"], hashlib.sha256,
    ).hexdigest()
    assert captured["headers"]["X-CMS-Signature"] == f"sha256={expected}"
    # Body must be valid JSON with the required fields
    payload = _json.loads(captured["body"])
    assert "case_id" in payload
    assert "callback_jwt" in payload
    assert payload["callback_url"].endswith("/api/v1/integrations/callbacks/n8n")


def test_trigger_workflow_n8n_unreachable_marks_failed():
    """httpx raises → run.status='failed' + error stamped + BusinessRuleError."""
    import asyncio as _aio
    import uuid as _uuid
    from unittest.mock import AsyncMock, MagicMock, patch
    import httpx as _httpx
    from sqlalchemy import text as _t
    from backend.src.core.exceptions import BusinessRuleError
    from backend.src.modules.n8n_bridge.application.use_cases import (
        N8nBridgeUseCases,
    )

    tenant_id = f"t-trig-down-{_uuid.uuid4().hex[:8]}"

    async def _go():
        from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
        from dotenv import dotenv_values
        env = dotenv_values("backend/.env")
        engine = create_async_engine(env["DATABASE_URL"])
        try:
            async with AsyncSession(engine, expire_on_commit=False) as session:
                await _seed_n8n_source(session, tenant_id, "down-secret")
                case_id = await _seed_minimal_case(session, tenant_id)

                async def _boom(*args, **kwargs):
                    raise _httpx.ConnectError("n8n is down")
                fake_client = MagicMock()
                fake_client.__aenter__ = AsyncMock(return_value=fake_client)
                fake_client.__aexit__ = AsyncMock(return_value=None)
                fake_client.post = AsyncMock(side_effect=_boom)

                with patch("httpx.AsyncClient", return_value=fake_client):
                    uc = N8nBridgeUseCases(
                        db=session, cms_base_url="https://cms.test",
                    )
                    with pytest.raises(BusinessRuleError):
                        await uc.trigger_workflow(
                            case_id=case_id,
                            workflow_url="https://n8n.test/webhook/down",
                        )
                row = (await session.execute(_t(
                    "SELECT status, error FROM playbook_runs "
                    "WHERE case_id = :cid"
                ), {"cid": case_id})).first()
                await _cleanup_n8n_tenant(session, tenant_id)
                return row
        finally:
            await engine.dispose()

    row = _aio.run(_go())
    assert row[0] == "failed"
    assert "ConnectError" in row[1]


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
