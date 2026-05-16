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
    # case_notes lives outside the n8n_bridge module but our add_note /
    # attach_artifact handlers populate it; delete first so the cases row
    # delete below doesn't fail an FK check.
    await session.execute(_t(
        "DELETE FROM case_notes WHERE case_id IN "
        "(SELECT id FROM cases WHERE tenant_id = :t)"
    ), {"t": tenant_id})
    for tbl in ("playbook_run_callbacks", "approval_requests",
                "playbook_runs", "cases", "integration_sources",
                "case_number_ranges", "security_taxonomies"):
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


# ── Task 5: Callback dispatcher ────────────────────────────────────────


async def _seed_playbook_run(session, case_id, tenant_id):
    """Insert a triggered playbook_run row and return its id."""
    import uuid as _uuid
    from sqlalchemy import text as _t
    run_id = str(_uuid.uuid4())
    await session.execute(_t(
        "INSERT INTO playbook_runs "
        "(id, tenant_id, case_id, workflow_url, triggered_at, triggered_by, "
        "status, callback_count, trigger_payload) "
        "VALUES (:id, :tid, :cid, 'https://n8n.test/wf', NOW(), 'manual', "
        "'triggered', 0, CAST('{}' AS json))"
    ), {"id": run_id, "tid": tenant_id, "cid": case_id})
    await session.commit()
    return run_id


def _hmac_header(body, secret):
    import hashlib
    import hmac as _hmac
    return "sha256=" + _hmac.new(
        secret.encode(), body, hashlib.sha256,
    ).hexdigest()


def test_callback_unknown_playbook_run_raises_not_found():
    """playbook_run_id that doesn't exist → NotFoundError."""
    import asyncio as _aio
    from backend.src.core.exceptions import NotFoundError
    from backend.src.modules.n8n_bridge.application.use_cases import (
        N8nBridgeUseCases,
    )

    async def _go():
        from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
        from dotenv import dotenv_values
        env = dotenv_values("backend/.env")
        engine = create_async_engine(env["DATABASE_URL"])
        try:
            async with AsyncSession(engine, expire_on_commit=False) as session:
                uc = N8nBridgeUseCases(db=session)
                with pytest.raises(NotFoundError):
                    await uc.handle_callback(
                        action="add_note", payload={},
                        playbook_run_id="00000000-0000-0000-0000-000000000000",
                        request_body=b'{}', request_headers={},
                    )
        finally:
            await engine.dispose()

    _aio.run(_go())


def test_callback_hmac_validation_rejects_wrong_signature():
    """Invalid HMAC header → UnauthorizedError + no state change."""
    import asyncio as _aio
    import uuid as _uuid
    from sqlalchemy import text as _t
    from backend.src.core.exceptions import UnauthorizedError
    from backend.src.modules.n8n_bridge.application.use_cases import (
        N8nBridgeUseCases,
    )

    tenant_id = f"t-cb-bad-{_uuid.uuid4().hex[:8]}"

    async def _go():
        from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
        from dotenv import dotenv_values
        env = dotenv_values("backend/.env")
        engine = create_async_engine(env["DATABASE_URL"])
        try:
            async with AsyncSession(engine, expire_on_commit=False) as session:
                await _seed_n8n_source(session, tenant_id, "real-secret")
                case_id = await _seed_minimal_case(session, tenant_id)
                run_id = await _seed_playbook_run(session, case_id, tenant_id)

                uc = N8nBridgeUseCases(db=session)
                with pytest.raises(UnauthorizedError):
                    await uc.handle_callback(
                        action="add_note", payload={"text": "x"},
                        playbook_run_id=run_id,
                        request_body=b'{"action":"add_note"}',
                        request_headers={
                            "x-cms-signature": "sha256=DEADBEEF",
                        },
                    )
                # Run state must NOT have advanced
                row = (await session.execute(_t(
                    "SELECT callback_count, status FROM playbook_runs "
                    "WHERE id = :id"
                ), {"id": run_id})).first()
                await _cleanup_n8n_tenant(session, tenant_id)
                return row
        finally:
            await engine.dispose()

    row = _aio.run(_go())
    assert row[0] == 0
    assert row[1] == "triggered"


def test_callback_unknown_action_logged_and_400():
    """Unknown action → ValidationError + callback row recorded with success=False."""
    import asyncio as _aio
    import uuid as _uuid
    from sqlalchemy import text as _t
    from backend.src.core.exceptions import ValidationError
    from backend.src.modules.n8n_bridge.application.use_cases import (
        N8nBridgeUseCases,
    )

    tenant_id = f"t-cb-bad-action-{_uuid.uuid4().hex[:8]}"
    secret = "unknown-action-secret"

    async def _go():
        from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
        from dotenv import dotenv_values
        env = dotenv_values("backend/.env")
        engine = create_async_engine(env["DATABASE_URL"])
        try:
            async with AsyncSession(engine, expire_on_commit=False) as session:
                await _seed_n8n_source(session, tenant_id, secret)
                case_id = await _seed_minimal_case(session, tenant_id)
                run_id = await _seed_playbook_run(session, case_id, tenant_id)

                body = b'{"action":"wat"}'
                headers = {"x-cms-signature": _hmac_header(body, secret)}

                uc = N8nBridgeUseCases(db=session)
                with pytest.raises(ValidationError):
                    await uc.handle_callback(
                        action="wat", payload={"action": "wat"},
                        playbook_run_id=run_id,
                        request_body=body, request_headers=headers,
                    )
                cb_row = (await session.execute(_t(
                    "SELECT action, success, error FROM playbook_run_callbacks "
                    "WHERE playbook_run_id = :id"
                ), {"id": run_id})).first()
                await _cleanup_n8n_tenant(session, tenant_id)
                return cb_row
        finally:
            await engine.dispose()

    cb = _aio.run(_go())
    assert cb[0] == "wat"
    assert cb[1] is False
    assert "unknown action" in (cb[2] or "").lower()


def test_callback_valid_transitions_triggered_to_running():
    """First valid callback transitions status triggered → running."""
    import asyncio as _aio
    import uuid as _uuid
    from sqlalchemy import text as _t
    from backend.src.modules.n8n_bridge.application.use_cases import (
        N8nBridgeUseCases,
    )

    tenant_id = f"t-cb-ok-{_uuid.uuid4().hex[:8]}"
    secret = "ok-secret"

    async def _go():
        from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
        from dotenv import dotenv_values
        env = dotenv_values("backend/.env")
        engine = create_async_engine(env["DATABASE_URL"])
        try:
            async with AsyncSession(engine, expire_on_commit=False) as session:
                await _seed_n8n_source(session, tenant_id, secret)
                case_id = await _seed_minimal_case(session, tenant_id)
                run_id = await _seed_playbook_run(session, case_id, tenant_id)

                # Use add_note with a valid payload so the test only verifies
                # the dispatcher path (state transition + counter + log).
                # Real action handlers are exercised in their own tests.
                payload = {"content": "dispatcher smoke"}
                body = _json.dumps({"action": "add_note", **payload}).encode()
                headers = {"x-cms-signature": _hmac_header(body, secret)}

                uc = _make_uc(session)
                response = await uc.handle_callback(
                    action="add_note", payload=payload,
                    playbook_run_id=run_id,
                    request_body=body, request_headers=headers,
                )
                row = (await session.execute(_t(
                    "SELECT status, callback_count, last_callback_at "
                    "FROM playbook_runs WHERE id = :id"
                ), {"id": run_id})).first()
                await _cleanup_n8n_tenant(session, tenant_id)
                return response, row
        finally:
            await engine.dispose()

    response, row = _aio.run(_go())
    assert response.get("ok") is True
    assert row[0] == "running"
    assert row[1] == 1
    assert row[2] is not None


# ── Task 6: Action handlers (update_case_field/priority/taxonomy/add_note) ──


def _make_uc(session):
    """Construct N8nBridgeUseCases with a system_user_id for handlers that
    need an actor (add_note inserts user_id)."""
    from backend.src.modules.n8n_bridge.application.use_cases import (
        N8nBridgeUseCases,
    )
    return N8nBridgeUseCases(
        db=session,
        cms_base_url="https://cms.test",
        system_user_id=ADMIN_USER_ID,
    )


def _hmac_callback(session_session, secret, action, payload):
    """Build the body+headers tuple used by every action test."""
    body = _json.dumps({"action": action, **payload}).encode()
    return body, {"x-cms-signature": _hmac_header(body, secret)}


def test_action_update_case_field_applies_allowlist():
    """title/description from payload land on the case row."""
    import asyncio as _aio
    import uuid as _uuid
    from sqlalchemy import text as _t

    tenant_id = f"t-act-uf-{_uuid.uuid4().hex[:8]}"
    secret = "uf-secret"

    async def _go():
        from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
        from dotenv import dotenv_values
        env = dotenv_values("backend/.env")
        engine = create_async_engine(env["DATABASE_URL"])
        try:
            async with AsyncSession(engine, expire_on_commit=False) as session:
                await _seed_n8n_source(session, tenant_id, secret)
                case_id = await _seed_minimal_case(session, tenant_id)
                run_id = await _seed_playbook_run(session, case_id, tenant_id)

                payload = {"title": "Updated by n8n", "description": "from playbook"}
                body, headers = _hmac_callback(session, secret, "update_case_field", payload)

                uc = _make_uc(session)
                response = await uc.handle_callback(
                    action="update_case_field", payload=payload,
                    playbook_run_id=run_id,
                    request_body=body, request_headers=headers,
                )
                row = (await session.execute(_t(
                    "SELECT title, description FROM cases WHERE id = :id"
                ), {"id": case_id})).first()
                await _cleanup_n8n_tenant(session, tenant_id)
                return response, row
        finally:
            await engine.dispose()

    response, row = _aio.run(_go())
    assert response["ok"] is True
    assert set(response["updated_fields"]) == {"title", "description"}
    assert row[0] == "Updated by n8n"
    assert row[1] == "from playbook"


def test_action_update_case_field_ignores_non_allowed_keys():
    """status_id (governance: terminal transitions require human) is silently dropped."""
    import asyncio as _aio
    import uuid as _uuid
    from sqlalchemy import text as _t

    tenant_id = f"t-act-block-{_uuid.uuid4().hex[:8]}"
    secret = "block-secret"

    async def _go():
        from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
        from dotenv import dotenv_values
        env = dotenv_values("backend/.env")
        engine = create_async_engine(env["DATABASE_URL"])
        try:
            async with AsyncSession(engine, expire_on_commit=False) as session:
                await _seed_n8n_source(session, tenant_id, secret)
                case_id = await _seed_minimal_case(session, tenant_id)
                run_id = await _seed_playbook_run(session, case_id, tenant_id)

                original_status = (await session.execute(_t(
                    "SELECT status_id FROM cases WHERE id = :id"
                ), {"id": case_id})).first()[0]

                payload = {"status_id": "should-be-ignored", "is_archived": True}
                body, headers = _hmac_callback(session, secret, "update_case_field", payload)

                uc = _make_uc(session)
                response = await uc.handle_callback(
                    action="update_case_field", payload=payload,
                    playbook_run_id=run_id,
                    request_body=body, request_headers=headers,
                )
                row = (await session.execute(_t(
                    "SELECT status_id, is_archived FROM cases WHERE id = :id"
                ), {"id": case_id})).first()
                await _cleanup_n8n_tenant(session, tenant_id)
                return response, row, original_status
        finally:
            await engine.dispose()

    response, row, original_status = _aio.run(_go())
    assert response.get("noop") is True
    assert row[0] == original_status
    assert row[1] is False


def test_action_update_priority_sets_priority_id():
    import asyncio as _aio
    import uuid as _uuid
    from sqlalchemy import text as _t

    tenant_id = f"t-act-pri-{_uuid.uuid4().hex[:8]}"
    secret = "pri-secret"

    async def _go():
        from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
        from dotenv import dotenv_values
        env = dotenv_values("backend/.env")
        engine = create_async_engine(env["DATABASE_URL"])
        try:
            async with AsyncSession(engine, expire_on_commit=False) as session:
                await _seed_n8n_source(session, tenant_id, secret)
                case_id = await _seed_minimal_case(session, tenant_id)
                run_id = await _seed_playbook_run(session, case_id, tenant_id)

                # Pick a different priority than the seeded one
                priorities = (await session.execute(_t(
                    "SELECT id FROM case_priorities ORDER BY level LIMIT 5"
                ))).all()
                current = (await session.execute(_t(
                    "SELECT priority_id FROM cases WHERE id = :id"
                ), {"id": case_id})).first()[0]
                new_pri = next(p[0] for p in priorities if p[0] != current)

                payload = {"priority_id": new_pri}
                body, headers = _hmac_callback(session, secret, "update_priority", payload)
                uc = _make_uc(session)
                await uc.handle_callback(
                    action="update_priority", payload=payload,
                    playbook_run_id=run_id,
                    request_body=body, request_headers=headers,
                )
                assigned = (await session.execute(_t(
                    "SELECT priority_id FROM cases WHERE id = :id"
                ), {"id": case_id})).first()[0]
                await _cleanup_n8n_tenant(session, tenant_id)
                return assigned, new_pri
        finally:
            await engine.dispose()

    assigned, expected = _aio.run(_go())
    assert assigned == expected


def test_action_update_taxonomy_sets_taxonomy_id():
    import asyncio as _aio
    import uuid as _uuid
    from sqlalchemy import text as _t

    tenant_id = f"t-act-tax-{_uuid.uuid4().hex[:8]}"
    secret = "tax-secret"

    async def _go():
        from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
        from dotenv import dotenv_values
        env = dotenv_values("backend/.env")
        engine = create_async_engine(env["DATABASE_URL"])
        try:
            async with AsyncSession(engine, expire_on_commit=False) as session:
                await _seed_n8n_source(session, tenant_id, secret)
                case_id = await _seed_minimal_case(session, tenant_id)
                run_id = await _seed_playbook_run(session, case_id, tenant_id)

                # Seed a taxonomy
                tax_id = str(_uuid.uuid4())
                await session.execute(_t(
                    "INSERT INTO security_taxonomies "
                    "(id, tenant_id, tuic_code, name, default_case_type, "
                    "requires_ticket, triage_mode, tlp_default, is_active, "
                    "created_at, updated_at, created_by, mitre_techniques) "
                    "VALUES (:id, :tid, :code, 'N8n Tax', 'event', false, "
                    "'auto', 'amber', true, NOW(), NOW(), :cb, "
                    "CAST('[]' AS json))"
                ), {
                    "id": tax_id, "tid": tenant_id,
                    "code": f"N8N-TAX-{_uuid.uuid4().hex[:6]}",
                    "cb": ADMIN_USER_ID,
                })
                await session.commit()

                payload = {"taxonomy_id": tax_id}
                body, headers = _hmac_callback(session, secret, "update_taxonomy", payload)
                uc = _make_uc(session)
                await uc.handle_callback(
                    action="update_taxonomy", payload=payload,
                    playbook_run_id=run_id,
                    request_body=body, request_headers=headers,
                )
                assigned = (await session.execute(_t(
                    "SELECT taxonomy_id FROM cases WHERE id = :id"
                ), {"id": case_id})).first()[0]
                await _cleanup_n8n_tenant(session, tenant_id)
                return assigned, tax_id
        finally:
            await engine.dispose()

    assigned, expected = _aio.run(_go())
    assert assigned == expected


def test_action_add_note_persists_with_playbook_marker():
    """add_note inserts case_notes row attributed to system user, content prefixed."""
    import asyncio as _aio
    import uuid as _uuid
    from sqlalchemy import text as _t

    tenant_id = f"t-act-note-{_uuid.uuid4().hex[:8]}"
    secret = "note-secret"

    async def _go():
        from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
        from dotenv import dotenv_values
        env = dotenv_values("backend/.env")
        engine = create_async_engine(env["DATABASE_URL"])
        try:
            async with AsyncSession(engine, expire_on_commit=False) as session:
                await _seed_n8n_source(session, tenant_id, secret)
                case_id = await _seed_minimal_case(session, tenant_id)
                run_id = await _seed_playbook_run(session, case_id, tenant_id)

                payload = {"content": "VirusTotal flagged hash abc as malicious"}
                body, headers = _hmac_callback(session, secret, "add_note", payload)

                uc = _make_uc(session)
                response = await uc.handle_callback(
                    action="add_note", payload=payload,
                    playbook_run_id=run_id,
                    request_body=body, request_headers=headers,
                )
                note = (await session.execute(_t(
                    "SELECT user_id, content FROM case_notes "
                    "WHERE case_id = :id"
                ), {"id": case_id})).first()
                await session.execute(_t(
                    "DELETE FROM case_notes WHERE case_id = :id"
                ), {"id": case_id})
                await _cleanup_n8n_tenant(session, tenant_id)
                return response, note, run_id
        finally:
            await engine.dispose()

    response, note, run_id = _aio.run(_go())
    assert response.get("ok") is True
    assert response.get("note_id")
    assert note[0] == ADMIN_USER_ID
    assert "VirusTotal" in note[1]
    assert run_id[:8] in note[1]  # short marker so operator can trace the n8n source


# ── Task 7: Action handler — request_approval ─────────────────────────


def test_action_request_approval_creates_pending_row():
    """request_approval payload → ApprovalRequestModel row with timeout_at set."""
    import asyncio as _aio
    import uuid as _uuid
    from datetime import datetime, timezone
    from sqlalchemy import text as _t

    tenant_id = f"t-act-appr-{_uuid.uuid4().hex[:8]}"
    secret = "appr-secret"

    async def _go():
        from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
        from dotenv import dotenv_values
        env = dotenv_values("backend/.env")
        engine = create_async_engine(env["DATABASE_URL"])
        try:
            async with AsyncSession(engine, expire_on_commit=False) as session:
                await _seed_n8n_source(session, tenant_id, secret)
                case_id = await _seed_minimal_case(session, tenant_id)
                run_id = await _seed_playbook_run(session, case_id, tenant_id)

                payload = {
                    "requested_action": "Aislar host PC-FIN-04 de la red",
                    "action_category": "host_quarantine",
                    "resume_url": "https://n8n.test/webhook-waiting/abc-123",
                    "timeout_minutes": 30,
                    "context": {"host": "PC-FIN-04", "ip": "10.0.0.5"},
                }
                body, headers = _hmac_callback(session, secret, "request_approval", payload)

                before = datetime.now(timezone.utc)
                uc = _make_uc(session)
                response = await uc.handle_callback(
                    action="request_approval", payload=payload,
                    playbook_run_id=run_id,
                    request_body=body, request_headers=headers,
                )
                row = (await session.execute(_t(
                    "SELECT id, status, requested_action, action_category, "
                    "resume_url, timeout_at, playbook_run_id, tenant_id, "
                    "case_id, context_payload FROM approval_requests "
                    "WHERE id = :id"
                ), {"id": response["approval_id"]})).first()
                await _cleanup_n8n_tenant(session, tenant_id)
                return response, row, before
        finally:
            await engine.dispose()

    response, row, before = _aio.run(_go())
    assert response["ok"] is True
    assert response["approval_id"]
    assert row[1] == "pending"
    assert row[2] == "Aislar host PC-FIN-04 de la red"
    assert row[3] == "host_quarantine"
    assert row[4] == "https://n8n.test/webhook-waiting/abc-123"
    # timeout_at should be roughly now + 30min
    timeout_dt = row[5]
    if timeout_dt.tzinfo is None:
        timeout_dt = timeout_dt.replace(tzinfo=timezone.utc)
    delta = (timeout_dt - before).total_seconds()
    assert 1700 <= delta <= 1900  # 30min ± some margin
    assert row[6] is not None  # playbook_run_id wired
    assert row[8] is not None  # case_id wired


def test_action_request_approval_uses_default_timeout_when_unspecified():
    import asyncio as _aio
    import uuid as _uuid
    from datetime import datetime, timezone
    from sqlalchemy import text as _t

    tenant_id = f"t-act-appr-def-{_uuid.uuid4().hex[:8]}"
    secret = "appr-def-secret"

    async def _go():
        from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
        from dotenv import dotenv_values
        env = dotenv_values("backend/.env")
        engine = create_async_engine(env["DATABASE_URL"])
        try:
            async with AsyncSession(engine, expire_on_commit=False) as session:
                await _seed_n8n_source(session, tenant_id, secret)
                case_id = await _seed_minimal_case(session, tenant_id)
                run_id = await _seed_playbook_run(session, case_id, tenant_id)

                payload = {
                    "requested_action": "Default-timeout test",
                    "action_category": "custom",
                    "resume_url": "https://n8n.test/wb/default",
                }
                body, headers = _hmac_callback(session, secret, "request_approval", payload)

                before = datetime.now(timezone.utc)
                uc = _make_uc(session)
                response = await uc.handle_callback(
                    action="request_approval", payload=payload,
                    playbook_run_id=run_id,
                    request_body=body, request_headers=headers,
                )
                row = (await session.execute(_t(
                    "SELECT timeout_at FROM approval_requests WHERE id = :id"
                ), {"id": response["approval_id"]})).first()
                await _cleanup_n8n_tenant(session, tenant_id)
                return row[0], before
        finally:
            await engine.dispose()

    timeout_dt, before = _aio.run(_go())
    if timeout_dt.tzinfo is None:
        timeout_dt = timeout_dt.replace(tzinfo=timezone.utc)
    delta = (timeout_dt - before).total_seconds()
    # Default is 60 minutes per spec — allow margin for test runtime
    assert 3500 <= delta <= 3700


def test_action_request_approval_missing_required_fields_raises():
    import asyncio as _aio
    import uuid as _uuid
    from backend.src.core.exceptions import ValidationError

    tenant_id = f"t-act-appr-bad-{_uuid.uuid4().hex[:8]}"
    secret = "appr-bad-secret"

    async def _go():
        from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
        from dotenv import dotenv_values
        env = dotenv_values("backend/.env")
        engine = create_async_engine(env["DATABASE_URL"])
        try:
            async with AsyncSession(engine, expire_on_commit=False) as session:
                await _seed_n8n_source(session, tenant_id, secret)
                case_id = await _seed_minimal_case(session, tenant_id)
                run_id = await _seed_playbook_run(session, case_id, tenant_id)

                # Missing 'resume_url' entirely
                payload = {
                    "requested_action": "no resume here",
                    "action_category": "custom",
                }
                body, headers = _hmac_callback(session, secret, "request_approval", payload)
                uc = _make_uc(session)
                with pytest.raises(ValidationError):
                    await uc.handle_callback(
                        action="request_approval", payload=payload,
                        playbook_run_id=run_id,
                        request_body=body, request_headers=headers,
                    )
                await _cleanup_n8n_tenant(session, tenant_id)
        finally:
            await engine.dispose()

    _aio.run(_go())


def test_action_request_approval_encrypts_resume_hmac_secret():
    """When payload includes resume_hmac_secret, it's stored as ciphertext."""
    import asyncio as _aio
    import uuid as _uuid
    from sqlalchemy import text as _t
    from backend.src.modules.integrations.application.crypto import decrypt_secret

    tenant_id = f"t-act-appr-enc-{_uuid.uuid4().hex[:8]}"
    secret = "appr-enc-secret"
    resume_secret = "n8n-resume-hmac-12345"

    async def _go():
        from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
        from dotenv import dotenv_values
        env = dotenv_values("backend/.env")
        engine = create_async_engine(env["DATABASE_URL"])
        try:
            async with AsyncSession(engine, expire_on_commit=False) as session:
                await _seed_n8n_source(session, tenant_id, secret)
                case_id = await _seed_minimal_case(session, tenant_id)
                run_id = await _seed_playbook_run(session, case_id, tenant_id)

                payload = {
                    "requested_action": "Encrypt test",
                    "action_category": "custom",
                    "resume_url": "https://n8n.test/wb/enc",
                    "resume_hmac_secret": resume_secret,
                }
                body, headers = _hmac_callback(session, secret, "request_approval", payload)
                uc = _make_uc(session)
                response = await uc.handle_callback(
                    action="request_approval", payload=payload,
                    playbook_run_id=run_id,
                    request_body=body, request_headers=headers,
                )
                row = (await session.execute(_t(
                    "SELECT resume_hmac_secret_encrypted FROM approval_requests "
                    "WHERE id = :id"
                ), {"id": response["approval_id"]})).first()
                await _cleanup_n8n_tenant(session, tenant_id)
                return row[0]
        finally:
            await engine.dispose()

    stored = _aio.run(_go())
    assert stored != resume_secret  # never plaintext
    assert decrypt_secret(stored) == resume_secret  # roundtrips through Fernet


# ── Task 8: record_decision terminal callback ─────────────────────────


def test_record_decision_marks_run_completed_with_decision():
    """decision='confirmed_as_event' → run.status='completed' + final_decision."""
    import asyncio as _aio
    import uuid as _uuid
    from sqlalchemy import text as _t

    tenant_id = f"t-dec-conf-{_uuid.uuid4().hex[:8]}"
    secret = "dec-conf-secret"

    async def _go():
        from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
        from dotenv import dotenv_values
        env = dotenv_values("backend/.env")
        engine = create_async_engine(env["DATABASE_URL"])
        try:
            async with AsyncSession(engine, expire_on_commit=False) as session:
                await _seed_n8n_source(session, tenant_id, secret)
                case_id = await _seed_minimal_case(session, tenant_id)
                run_id = await _seed_playbook_run(session, case_id, tenant_id)

                payload = {"decision": "confirmed_as_event", "summary": "no malware"}
                body, headers = _hmac_callback(session, secret, "record_decision", payload)

                uc = _make_uc(session)
                response = await uc.handle_callback(
                    action="record_decision", payload=payload,
                    playbook_run_id=run_id,
                    request_body=body, request_headers=headers,
                )
                row = (await session.execute(_t(
                    "SELECT status, final_decision, completed_at, "
                    "final_decision_data FROM playbook_runs WHERE id = :id"
                ), {"id": run_id})).first()
                await _cleanup_n8n_tenant(session, tenant_id)
                return response, row
        finally:
            await engine.dispose()

    response, row = _aio.run(_go())
    assert response["ok"] is True
    assert response["decision"] == "confirmed_as_event"
    assert row[0] == "completed"
    assert row[1] == "confirmed_as_event"
    assert row[2] is not None  # completed_at stamped
    assert row[3]["summary"] == "no malware"


def test_record_decision_discarded_updates_case_status():
    """decision='discarded' → case.status changes to 'discarded'."""
    import asyncio as _aio
    import uuid as _uuid
    from sqlalchemy import text as _t

    tenant_id = f"t-dec-disc-{_uuid.uuid4().hex[:8]}"
    secret = "dec-disc-secret"

    async def _go():
        from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
        from dotenv import dotenv_values
        env = dotenv_values("backend/.env")
        engine = create_async_engine(env["DATABASE_URL"])
        try:
            async with AsyncSession(engine, expire_on_commit=False) as session:
                await _seed_n8n_source(session, tenant_id, secret)
                case_id = await _seed_minimal_case(session, tenant_id)
                run_id = await _seed_playbook_run(session, case_id, tenant_id)

                payload = {"decision": "discarded", "reason": "false positive"}
                body, headers = _hmac_callback(session, secret, "record_decision", payload)

                uc = _make_uc(session)
                await uc.handle_callback(
                    action="record_decision", payload=payload,
                    playbook_run_id=run_id,
                    request_body=body, request_headers=headers,
                )
                case_status = (await session.execute(_t(
                    "SELECT cs.slug FROM cases c "
                    "JOIN case_statuses cs ON cs.id = c.status_id "
                    "WHERE c.id = :id"
                ), {"id": case_id})).first()[0]
                await _cleanup_n8n_tenant(session, tenant_id)
                return case_status
        finally:
            await engine.dispose()

    assert _aio.run(_go()) == "discarded"


def test_record_decision_unknown_value_rejected():
    """decision='resolved' (not in allowlist) → ValidationError (n8n can't close)."""
    import asyncio as _aio
    import uuid as _uuid
    from backend.src.core.exceptions import ValidationError

    tenant_id = f"t-dec-bad-{_uuid.uuid4().hex[:8]}"
    secret = "dec-bad-secret"

    async def _go():
        from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
        from dotenv import dotenv_values
        env = dotenv_values("backend/.env")
        engine = create_async_engine(env["DATABASE_URL"])
        try:
            async with AsyncSession(engine, expire_on_commit=False) as session:
                await _seed_n8n_source(session, tenant_id, secret)
                case_id = await _seed_minimal_case(session, tenant_id)
                run_id = await _seed_playbook_run(session, case_id, tenant_id)

                payload = {"decision": "resolved"}  # forbidden
                body, headers = _hmac_callback(session, secret, "record_decision", payload)

                uc = _make_uc(session)
                with pytest.raises(ValidationError):
                    await uc.handle_callback(
                        action="record_decision", payload=payload,
                        playbook_run_id=run_id,
                        request_body=body, request_headers=headers,
                    )
                await _cleanup_n8n_tenant(session, tenant_id)
        finally:
            await engine.dispose()

    _aio.run(_go())


def test_record_decision_idempotent_when_run_already_completed():
    """Second record_decision call on completed run returns noop."""
    import asyncio as _aio
    import uuid as _uuid
    from sqlalchemy import text as _t

    tenant_id = f"t-dec-idem-{_uuid.uuid4().hex[:8]}"
    secret = "dec-idem-secret"

    async def _go():
        from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
        from dotenv import dotenv_values
        env = dotenv_values("backend/.env")
        engine = create_async_engine(env["DATABASE_URL"])
        try:
            async with AsyncSession(engine, expire_on_commit=False) as session:
                await _seed_n8n_source(session, tenant_id, secret)
                case_id = await _seed_minimal_case(session, tenant_id)
                run_id = await _seed_playbook_run(session, case_id, tenant_id)

                payload = {"decision": "confirmed_as_event"}
                body, headers = _hmac_callback(session, secret, "record_decision", payload)

                uc = _make_uc(session)
                first = await uc.handle_callback(
                    action="record_decision", payload=payload,
                    playbook_run_id=run_id,
                    request_body=body, request_headers=headers,
                )
                second = await uc.handle_callback(
                    action="record_decision", payload=payload,
                    playbook_run_id=run_id,
                    request_body=body, request_headers=headers,
                )
                cb_count = (await session.execute(_t(
                    "SELECT callback_count FROM playbook_runs WHERE id = :id"
                ), {"id": run_id})).first()[0]
                await _cleanup_n8n_tenant(session, tenant_id)
                return first, second, cb_count
        finally:
            await engine.dispose()

    first, second, cb_count = _aio.run(_go())
    assert first["ok"] is True
    assert first.get("noop") is not True
    assert second["ok"] is True
    assert second.get("noop") is True
    # Both callbacks counted (audit trail intact), but case state only mutated once
    assert cb_count == 2


# ── Task 9: attach_artifact + set_pending_triage_complete ──────────────


def test_action_attach_artifact_creates_note_marker():
    """attach_artifact stub records a note describing the artifact reference."""
    import asyncio as _aio
    import uuid as _uuid
    from sqlalchemy import text as _t

    tenant_id = f"t-act-art-{_uuid.uuid4().hex[:8]}"
    secret = "art-secret"

    async def _go():
        from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
        from dotenv import dotenv_values
        env = dotenv_values("backend/.env")
        engine = create_async_engine(env["DATABASE_URL"])
        try:
            async with AsyncSession(engine, expire_on_commit=False) as session:
                await _seed_n8n_source(session, tenant_id, secret)
                case_id = await _seed_minimal_case(session, tenant_id)
                run_id = await _seed_playbook_run(session, case_id, tenant_id)

                payload = {
                    "artifact_type": "velociraptor_collection",
                    "artifact_ref": "vc-flow-abc-123",
                    "summary": "Memory dump from PC-FIN-04",
                }
                body, headers = _hmac_callback(session, secret, "attach_artifact", payload)

                uc = _make_uc(session)
                response = await uc.handle_callback(
                    action="attach_artifact", payload=payload,
                    playbook_run_id=run_id,
                    request_body=body, request_headers=headers,
                )
                note = (await session.execute(_t(
                    "SELECT content FROM case_notes WHERE case_id = :id "
                    "ORDER BY created_at DESC LIMIT 1"
                ), {"id": case_id})).first()
                await session.execute(_t(
                    "DELETE FROM case_notes WHERE case_id = :id"
                ), {"id": case_id})
                await _cleanup_n8n_tenant(session, tenant_id)
                return response, note
        finally:
            await engine.dispose()

    response, note = _aio.run(_go())
    assert response["ok"] is True
    assert response.get("artifact_type") == "velociraptor_collection"
    assert response.get("artifact_ref") == "vc-flow-abc-123"
    assert "[n8n run" in note[0]
    assert "velociraptor_collection" in note[0]
    assert "vc-flow-abc-123" in note[0]


def test_action_set_pending_triage_complete_transitions_to_logged():
    """case in pending_triage → set_pending_triage_complete → status='logged'."""
    import asyncio as _aio
    import uuid as _uuid
    from sqlalchemy import text as _t

    tenant_id = f"t-act-trg-{_uuid.uuid4().hex[:8]}"
    secret = "trg-secret"

    async def _go():
        from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
        from dotenv import dotenv_values
        env = dotenv_values("backend/.env")
        engine = create_async_engine(env["DATABASE_URL"])
        try:
            async with AsyncSession(engine, expire_on_commit=False) as session:
                await _seed_n8n_source(session, tenant_id, secret)
                case_id = await _seed_minimal_case(session, tenant_id)
                run_id = await _seed_playbook_run(session, case_id, tenant_id)

                # Force case into pending_triage status
                pt_status = (await session.execute(_t(
                    "SELECT id FROM case_statuses WHERE slug = 'pending_triage'"
                ))).first()[0]
                await session.execute(_t(
                    "UPDATE cases SET status_id = :s, "
                    "pending_triage_until = NOW() + INTERVAL '10 minutes' "
                    "WHERE id = :id"
                ), {"s": pt_status, "id": case_id})
                await session.commit()

                body, headers = _hmac_callback(
                    session, secret, "set_pending_triage_complete", {},
                )
                uc = _make_uc(session)
                response = await uc.handle_callback(
                    action="set_pending_triage_complete", payload={},
                    playbook_run_id=run_id,
                    request_body=body, request_headers=headers,
                )
                row = (await session.execute(_t(
                    "SELECT cs.slug, c.pending_triage_until FROM cases c "
                    "JOIN case_statuses cs ON cs.id = c.status_id "
                    "WHERE c.id = :id"
                ), {"id": case_id})).first()
                await _cleanup_n8n_tenant(session, tenant_id)
                return response, row
        finally:
            await engine.dispose()

    response, row = _aio.run(_go())
    assert response["ok"] is True
    assert response.get("transitioned") is True
    assert row[0] == "logged"
    assert row[1] is None


def test_action_set_pending_triage_complete_noop_on_other_status():
    """If case status != 'pending_triage', the action is a noop."""
    import asyncio as _aio
    import uuid as _uuid
    from sqlalchemy import text as _t

    tenant_id = f"t-act-trg-noop-{_uuid.uuid4().hex[:8]}"
    secret = "trg-noop-secret"

    async def _go():
        from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
        from dotenv import dotenv_values
        env = dotenv_values("backend/.env")
        engine = create_async_engine(env["DATABASE_URL"])
        try:
            async with AsyncSession(engine, expire_on_commit=False) as session:
                await _seed_n8n_source(session, tenant_id, secret)
                case_id = await _seed_minimal_case(session, tenant_id)
                run_id = await _seed_playbook_run(session, case_id, tenant_id)

                original_status = (await session.execute(_t(
                    "SELECT status_id FROM cases WHERE id = :id"
                ), {"id": case_id})).first()[0]

                body, headers = _hmac_callback(
                    session, secret, "set_pending_triage_complete", {},
                )
                uc = _make_uc(session)
                response = await uc.handle_callback(
                    action="set_pending_triage_complete", payload={},
                    playbook_run_id=run_id,
                    request_body=body, request_headers=headers,
                )
                current_status = (await session.execute(_t(
                    "SELECT status_id FROM cases WHERE id = :id"
                ), {"id": case_id})).first()[0]
                await _cleanup_n8n_tenant(session, tenant_id)
                return response, current_status, original_status
        finally:
            await engine.dispose()

    response, current, original = _aio.run(_go())
    assert response["ok"] is True
    assert response.get("noop") is True
    assert current == original


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
