"""E2E integration tests for Sub-spec 05 (Plan 05 Task 13).

Drives the full pipeline through HTTP:
- Operator triggers a playbook via POST /cases/{id}/trigger-workflow (mocked n8n)
- n8n posts back to /callbacks/n8n with HMAC-signed body
- Approval decisions go through /approval-requests/{id}/decide

Shares fixtures with the unit-test file at the module level so the env vars
required by the use cases (encryption key, system user) are set before any
n8n_bridge import resolves.
"""
import asyncio
import hashlib
import hmac
import json
import os
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


os.environ.setdefault(
    "INTEGRATIONS_ENCRYPTION_KEY",
    "Uf0yMQkQS7qc_AQVDGFYNc8Lc4E4l0QYtVkk4IZ5tXU=",
)
os.environ.setdefault(
    "INTEGRATIONS_SYSTEM_USER_ID",
    "ec35a91e-5778-4210-a631-c5ed673c679d",
)

ADMIN_USER_ID = "ec35a91e-5778-4210-a631-c5ed673c679d"


# ── Test fixtures ──────────────────────────────────────────────────────


def _run(coro):
    return asyncio.run(coro)


def _get_real_url():
    from dotenv import dotenv_values
    env = dotenv_values("backend/.env")
    url = env.get("DATABASE_URL")
    if not url:
        pytest.skip("DATABASE_URL not in backend/.env")
    return url


def _bind_app_to_real_db():
    """Override get_db so the conftest sandbox fake URL doesn't block routes."""
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from backend.src.main import app
    from backend.src.core.database import get_db

    engine = create_async_engine(_get_real_url())
    Session = async_sessionmaker(engine, expire_on_commit=False)

    async def _override():
        async with Session() as session:
            yield session

    app.dependency_overrides[get_db] = _override

    def _cleanup():
        app.dependency_overrides.pop(get_db, None)

    return app, engine, _cleanup


async def _open_session():
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    engine = create_async_engine(_get_real_url())
    session = AsyncSession(engine, expire_on_commit=False)
    return engine, session


async def _make_jwt(session, role_name="Super Admin", user_id=ADMIN_USER_ID):
    """Mint a JWT for the admin endpoints."""
    from sqlalchemy import text as _t
    from backend.src.core.security import create_access_token
    row = (await session.execute(_t(
        "SELECT id, level FROM roles WHERE name = :n AND tenant_id IS NULL LIMIT 1"
    ), {"n": role_name})).first()
    if not row:
        pytest.skip(f"Role '{role_name}' missing in dev seed")
    return create_access_token(
        subject=user_id,
        extra_claims={
            "role_id": row[0],
            "role_level": int(row[1]),
            "tenant_id": "e2e-tenant",
            "email": "e2e@test.local",
        },
    )


async def _setup_case_with_n8n_source(session, tenant_id, secret):
    """Insert source + minimal case + return ids."""
    from sqlalchemy import text as _t
    from backend.src.modules.integrations.application.crypto import encrypt_secret

    # Pre-seed case_number_ranges
    for prefix in ("EVT", "INC"):
        await session.execute(_t(
            "INSERT INTO case_number_ranges "
            "(id, tenant_id, case_type, prefix, range_start, range_end, "
            "current_number, created_at) "
            "VALUES (:id, :t, "
            "CASE :p WHEN 'INC' THEN 'incident' WHEN 'REQ' THEN 'request' ELSE 'event' END, "
            ":p, 1, 999999, 0, NOW())"
        ), {"id": str(uuid.uuid4()), "t": tenant_id, "p": prefix})
    await session.commit()

    # n8n integration_source
    source_id = str(uuid.uuid4())
    await session.execute(_t(
        "INSERT INTO integration_sources "
        "(id, tenant_id, name, source_type, auth_method, auth_secret_encrypted, "
        "auth_header_name, is_active, total_events_received, total_events_failed, "
        "created_at, updated_at, created_by) "
        "VALUES (:id, :tid, 'e2e-n8n', 'n8n', 'hmac', :sec, 'X-CMS-Signature', "
        "true, 0, 0, NOW(), NOW(), :cb)"
    ), {
        "id": source_id, "tid": tenant_id,
        "sec": encrypt_secret(secret), "cb": ADMIN_USER_ID,
    })

    # Minimal case
    svc_id = (await session.execute(_t(
        "SELECT id FROM service_catalog_items LIMIT 1"
    ))).first()[0]
    pri_id = (await session.execute(_t(
        "SELECT id FROM case_priorities LIMIT 1"
    ))).first()[0]
    status_id = (await session.execute(_t(
        "SELECT id FROM case_statuses WHERE slug = 'logged' LIMIT 1"
    ))).first()[0]
    case_id = str(uuid.uuid4())
    await session.execute(_t(
        "INSERT INTO cases "
        "(id, tenant_id, case_number, title, status_id, priority_id, "
        "complexity, current_level, service_item_id, created_by, is_archived, "
        "case_type, created_at, updated_at) "
        "VALUES (:id, :tid, :cn, 'E2E case', :sid, :pid, 'simple', 1, "
        ":svc, :cb, false, 'event', NOW(), NOW())"
    ), {
        "id": case_id, "tid": tenant_id,
        "cn": f"EVT-2099-{uuid.uuid4().hex[:6]}",
        "sid": status_id, "pid": pri_id, "svc": svc_id, "cb": ADMIN_USER_ID,
    })
    await session.commit()
    return source_id, case_id


async def _cleanup_tenant(session, tenant_id):
    from sqlalchemy import text as _t
    await session.execute(_t(
        "DELETE FROM case_notes WHERE case_id IN "
        "(SELECT id FROM cases WHERE tenant_id = :t)"
    ), {"t": tenant_id})
    for tbl in (
        "playbook_run_callbacks", "approval_requests", "playbook_runs",
        "cases", "integration_sources", "case_number_ranges",
    ):
        where = (
            "playbook_run_id IN (SELECT id FROM playbook_runs WHERE tenant_id = :t)"
            if tbl == "playbook_run_callbacks" else "tenant_id = :t"
        )
        await session.execute(_t(f"DELETE FROM {tbl} WHERE {where}"), {"t": tenant_id})
    await session.commit()


def _sign(body: bytes, secret: str) -> str:
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


# ── E2E #1: trigger via HTTP → callback via HTTP ──────────────────────


def test_e2e_trigger_then_callback_full_pipeline():
    """Operator triggers via /cases/{id}/trigger-workflow → mock n8n accepts →
    n8n posts back add_note via /callbacks/n8n → assert run state + note."""
    from httpx import AsyncClient, ASGITransport

    tenant_id = f"e2e-pipe-{uuid.uuid4().hex[:8]}"
    secret = "e2e-pipe-secret"

    async def _go():
        app, app_engine, cleanup = _bind_app_to_real_db()
        eng, session = await _open_session()
        try:
            source_id, case_id = await _setup_case_with_n8n_source(
                session, tenant_id, secret,
            )
            token = await _make_jwt(session)

            # Stub the outbound trigger to n8n
            trigger_resp = MagicMock()
            trigger_resp.status_code = 200
            trigger_resp.content = b'{"executionId": "e2e-exec-1"}'
            trigger_resp.json = MagicMock(return_value={"executionId": "e2e-exec-1"})
            trigger_resp.raise_for_status = MagicMock(return_value=None)
            fake_client = MagicMock()
            fake_client.__aenter__ = AsyncMock(return_value=fake_client)
            fake_client.__aexit__ = AsyncMock(return_value=None)
            fake_client.post = AsyncMock(return_value=trigger_resp)

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as http:
                # Step 1: operator triggers
                with patch("httpx.AsyncClient", return_value=fake_client):
                    r1 = await http.post(
                        f"/api/v1/cases/{case_id}/trigger-workflow",
                        json={"workflow_url": "https://n8n.test/wb/e2e-pipe"},
                        headers={"Authorization": f"Bearer {token}"},
                    )
                assert r1.status_code == 201, r1.text
                run_id = r1.json()["data"]["id"]

                # Step 2: n8n posts back add_note
                cb_payload = {
                    "action": "add_note",
                    "playbook_run_id": run_id,
                    "payload": {"content": "VirusTotal scan complete"},
                }
                body = json.dumps(cb_payload).encode()
                r2 = await http.post(
                    "/api/v1/integrations/callbacks/n8n",
                    content=body,
                    headers={
                        "content-type": "application/json",
                        "x-cms-signature": _sign(body, secret),
                    },
                )
                assert r2.status_code == 200, r2.text

            # Verify state
            from sqlalchemy import text as _t
            run_status = (await session.execute(_t(
                "SELECT status, callback_count FROM playbook_runs WHERE id = :id"
            ), {"id": run_id})).first()
            note = (await session.execute(_t(
                "SELECT content FROM case_notes WHERE case_id = :id "
                "ORDER BY created_at DESC LIMIT 1"
            ), {"id": case_id})).first()
            return run_status, note
        finally:
            await _cleanup_tenant(session, tenant_id)
            await session.close()
            await eng.dispose()
            cleanup()
            await app_engine.dispose()

    run_status, note = _run(_go())
    assert run_status[0] == "running"  # transitioned after first callback
    assert run_status[1] == 1
    assert "VirusTotal" in note[0]


# ── E2E #2: approval decide POSTs to resume_url ───────────────────────


def test_e2e_approval_decide_via_http_resumes_n8n():
    """Operator approves via HTTP → CMS POSTs to mocked resume_url with HMAC."""
    from httpx import AsyncClient, ASGITransport

    tenant_id = f"e2e-appr-{uuid.uuid4().hex[:8]}"
    secret = "e2e-appr-secret"
    resume_secret = "n8n-resume-shared"

    async def _go():
        app, app_engine, cleanup = _bind_app_to_real_db()
        eng, session = await _open_session()
        try:
            from sqlalchemy import text as _t
            from backend.src.modules.integrations.application.crypto import encrypt_secret

            _, case_id = await _setup_case_with_n8n_source(
                session, tenant_id, secret,
            )
            # Manually seed a playbook_run + approval (skip the trigger step)
            run_id = str(uuid.uuid4())
            await session.execute(_t(
                "INSERT INTO playbook_runs "
                "(id, tenant_id, case_id, workflow_url, triggered_at, "
                "triggered_by, status, callback_count, trigger_payload) "
                "VALUES (:id, :tid, :cid, 'https://n8n.test/wb', NOW(), "
                "'manual', 'running', 0, CAST('{}' AS json))"
            ), {"id": run_id, "tid": tenant_id, "cid": case_id})
            approval_id = str(uuid.uuid4())
            await session.execute(_t(
                "INSERT INTO approval_requests "
                "(id, tenant_id, case_id, playbook_run_id, requested_action, "
                "action_category, context_payload, requested_by_workflow, "
                "resume_url, resume_hmac_secret_encrypted, status, timeout_at, "
                "resume_succeeded, created_at) "
                "VALUES (:id, :tid, :cid, :rid, 'Quarantine host', "
                "'host_quarantine', CAST('{\"host\":\"PC-FIN-04\"}' AS json), "
                "'https://n8n.test/wb', 'https://n8n.test/resume-e2e', :sec, "
                "'pending', :to_at, false, NOW())"
            ), {
                "id": approval_id, "tid": tenant_id, "cid": case_id, "rid": run_id,
                "sec": encrypt_secret(resume_secret),
                "to_at": datetime.now(timezone.utc) + timedelta(hours=1),
            })
            await session.commit()

            token = await _make_jwt(session)

            # Mock the resume POST
            captured = {}
            async def _post(url, **kwargs):
                captured["url"] = url
                captured["body"] = kwargs.get("content")
                captured["headers"] = kwargs.get("headers")
                resp = MagicMock()
                resp.status_code = 200
                resp.content = b"{}"
                resp.json = MagicMock(return_value={})
                resp.raise_for_status = MagicMock(return_value=None)
                return resp

            fake = MagicMock()
            fake.__aenter__ = AsyncMock(return_value=fake)
            fake.__aexit__ = AsyncMock(return_value=None)
            fake.post = AsyncMock(side_effect=_post)

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as http:
                with patch("httpx.AsyncClient", return_value=fake):
                    r = await http.post(
                        f"/api/v1/approval-requests/{approval_id}/decide",
                        json={"decision": "approved"},
                        headers={"Authorization": f"Bearer {token}"},
                    )
            assert r.status_code == 200, r.text

            # Verify the resume POST landed at the right URL with HMAC
            assert captured["url"] == "https://n8n.test/resume-e2e"
            assert captured["headers"].get("X-CMS-Signature", "").startswith("sha256=")

            # Verify decision persisted
            row = (await session.execute(_t(
                "SELECT status, resume_succeeded FROM approval_requests "
                "WHERE id = :id"
            ), {"id": approval_id})).first()
            return row, captured
        finally:
            await _cleanup_tenant(session, tenant_id)
            await session.close()
            await eng.dispose()
            cleanup()
            await app_engine.dispose()

    row, captured = _run(_go())
    assert row[0] == "approved"
    assert row[1] is True
    body = json.loads(captured["body"])
    assert body["decision"] == "approved"
    assert body["approver_user_id"] == ADMIN_USER_ID


# ── E2E #3: callback for unknown run returns 404 ──────────────────────


def test_e2e_callback_unknown_run_returns_404():
    from httpx import AsyncClient, ASGITransport

    async def _go():
        app, app_engine, cleanup = _bind_app_to_real_db()
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as http:
                body = json.dumps({
                    "action": "add_note",
                    "playbook_run_id": "00000000-0000-0000-0000-000000000000",
                    "payload": {"content": "ghost"},
                }).encode()
                return await http.post(
                    "/api/v1/integrations/callbacks/n8n",
                    content=body,
                    headers={"content-type": "application/json"},
                )
        finally:
            cleanup()
            await app_engine.dispose()

    resp = _run(_go())
    assert resp.status_code == 404


# ── E2E #4: trigger fails when n8n is unreachable → 502 ────────────────


def test_e2e_trigger_n8n_unreachable_returns_502():
    from httpx import AsyncClient, ASGITransport
    import httpx as _httpx

    tenant_id = f"e2e-down-{uuid.uuid4().hex[:8]}"
    secret = "e2e-down-secret"

    async def _go():
        app, app_engine, cleanup = _bind_app_to_real_db()
        eng, session = await _open_session()
        try:
            _, case_id = await _setup_case_with_n8n_source(
                session, tenant_id, secret,
            )
            token = await _make_jwt(session)

            async def _boom(*a, **kw):
                raise _httpx.ConnectError("n8n down")
            fake = MagicMock()
            fake.__aenter__ = AsyncMock(return_value=fake)
            fake.__aexit__ = AsyncMock(return_value=None)
            fake.post = AsyncMock(side_effect=_boom)

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as http:
                with patch("httpx.AsyncClient", return_value=fake):
                    r = await http.post(
                        f"/api/v1/cases/{case_id}/trigger-workflow",
                        json={"workflow_url": "https://n8n.dead/wb"},
                        headers={"Authorization": f"Bearer {token}"},
                    )
            return r.status_code
        finally:
            await _cleanup_tenant(session, tenant_id)
            await session.close()
            await eng.dispose()
            cleanup()
            await app_engine.dispose()

    assert _run(_go()) == 502
