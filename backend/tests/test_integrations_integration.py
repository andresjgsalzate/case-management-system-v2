"""End-to-end integration tests for Sub-spec 04 (Plan 04 Task 15).

These tests drive the full pipeline through HTTP:
  POST /api/v1/integrations/sources/{id}/events  (HMAC-signed real Wazuh JSON)
    → receive_event persists inbound row
    → retry_pending_events_once (in-test, no APScheduler) → process_event
    → assert case exists in DB with the expected fields

They share the test infra from `test_integrations_wazuh.py` (env vars set
at module import time and the `_cleanup_by_tenant` helper).
"""
import asyncio
import hashlib
import hmac
import json
import os
import uuid
from pathlib import Path

import pytest


# Match the test fixtures in test_integrations_wazuh.py — these vars must be
# set BEFORE any module that reads them gets imported.
os.environ.setdefault(
    "INTEGRATIONS_ENCRYPTION_KEY",
    "Uf0yMQkQS7qc_AQVDGFYNc8Lc4E4l0QYtVkk4IZ5tXU=",
)
os.environ.setdefault(
    "INTEGRATIONS_SYSTEM_USER_ID",
    "ec35a91e-5778-4210-a631-c5ed673c679d",
)

FIXTURES = Path(__file__).parent / "fixtures" / "wazuh_payloads"
ADMIN_USER_ID = "ec35a91e-5778-4210-a631-c5ed673c679d"


# ── Helpers ────────────────────────────────────────────────────────────


def _run(coro):
    return asyncio.run(coro)


def _sign_hmac(body: bytes, secret: str) -> str:
    return "sha256=" + hmac.new(
        secret.encode(), body, hashlib.sha256,
    ).hexdigest()


def _get_real_url():
    from dotenv import dotenv_values
    env = dotenv_values("backend/.env")
    url = env.get("DATABASE_URL")
    if not url:
        pytest.skip("DATABASE_URL not in backend/.env")
    return url


async def _open_session():
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    engine = create_async_engine(_get_real_url())
    session = AsyncSession(engine, expire_on_commit=False)
    return engine, session


async def _seed_source_with_hmac(
    session, *, tenant_id, default_service_item_id, default_priority_id,
    secret: str,
):
    from sqlalchemy import text as _t
    from backend.src.modules.integrations.application.crypto import (
        encrypt_secret,
    )
    source_id = str(uuid.uuid4())
    await session.execute(_t(
        "INSERT INTO integration_sources "
        "(id, tenant_id, name, source_type, auth_method, auth_secret_encrypted, "
        "auth_header_name, default_service_item_id, default_priority_id, "
        "is_active, total_events_received, total_events_failed, "
        "created_at, updated_at, created_by) "
        "VALUES (:id, :tid, :name, 'wazuh', 'hmac', :secret, "
        "'X-CMS-Signature', :svc, :pri, true, 0, 0, NOW(), NOW(), :cb)"
    ), {
        "id": source_id, "tid": tenant_id,
        "name": f"e2e-source-{source_id[:8]}",
        "secret": encrypt_secret(secret),
        "svc": default_service_item_id, "pri": default_priority_id,
        "cb": ADMIN_USER_ID,
    })
    await session.commit()
    return source_id


async def _setup_common(session, tenant_id, payload):
    """Returns (source_id, taxonomy_id, mapping_id, svc_item_id_used)."""
    from sqlalchemy import text as _t

    # Pick existing rows from dev seed
    svc_id = (await session.execute(_t(
        "SELECT id FROM service_catalog_items LIMIT 1"
    ))).first()[0]
    pri_id = (await session.execute(_t(
        "SELECT id FROM case_priorities LIMIT 1"
    ))).first()[0]

    # Pre-seed case_number ranges for this tenant
    for prefix in ("EVT", "INC", "REQ"):
        await session.execute(_t(
            "INSERT INTO case_number_ranges "
            "(id, tenant_id, prefix, range_start, range_end, "
            "current_number, created_at) "
            "VALUES (:id, :t, :p, 1, 999999, 0, NOW())"
        ), {"id": str(uuid.uuid4()), "t": tenant_id, "p": prefix})
    await session.commit()

    # Taxonomy with default catalog mapping
    tax_id = str(uuid.uuid4())
    await session.execute(_t(
        "INSERT INTO security_taxonomies "
        "(id, tenant_id, tuic_code, name, default_case_type, requires_ticket, "
        "triage_mode, tlp_default, is_active, created_at, updated_at, "
        "created_by, mitre_techniques) "
        "VALUES (:id, :tid, :code, 'E2E Tax', 'incident', false, 'auto', "
        "'amber', true, NOW(), NOW(), :cb, CAST('[]' AS json))"
    ), {
        "id": tax_id, "tid": tenant_id,
        "code": f"E2E-TAX-{uuid.uuid4().hex[:6]}", "cb": ADMIN_USER_ID,
    })
    await session.execute(_t(
        "INSERT INTO taxonomy_catalog_mappings "
        "(id, taxonomy_id, service_catalog_item_id, is_default, priority_order) "
        "VALUES (:id, :tax, :svc, true, 0)"
    ), {"id": str(uuid.uuid4()), "tax": tax_id, "svc": svc_id})

    # Wazuh rule_id mapping
    mapping_id = str(uuid.uuid4())
    await session.execute(_t(
        "INSERT INTO wazuh_rule_to_taxonomy_map "
        "(id, tenant_id, source_id, match_strategy, match_value, taxonomy_id, "
        "priority_order, is_active, created_at, updated_at, created_by) "
        "VALUES (:id, :tid, NULL, 'rule_id', CAST(:v AS json), :tax, "
        "1000, true, NOW(), NOW(), :cb)"
    ), {
        "id": mapping_id, "tid": tenant_id,
        "v": json.dumps({"value": payload["rule"]["id"]}),
        "tax": tax_id, "cb": ADMIN_USER_ID,
    })
    await session.commit()
    return svc_id, pri_id, tax_id, mapping_id


async def _cleanup_tenant(session, tenant_id):
    from sqlalchemy import text as _t
    for tbl in ("cases", "inbound_events", "integration_sources",
                "case_number_ranges", "wazuh_rule_to_taxonomy_map",
                "security_taxonomies"):
        await session.execute(_t(
            f"DELETE FROM {tbl} WHERE tenant_id = :t"
        ), {"t": tenant_id})
    await session.commit()


async def _post_webhook(app, source_id, body, signature):
    from httpx import AsyncClient, ASGITransport
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.post(
            f"/api/v1/integrations/sources/{source_id}/events",
            content=body,
            headers={
                "Content-Type": "application/json",
                "X-CMS-Signature": signature,
            },
        )


def _bind_app_to_real_db():
    """Override FastAPI's get_db dep to use the real backend/.env DATABASE_URL.
    The conftest sandbox uses a fake URL the E2E webhook can't talk to."""
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from backend.src.main import app
    from backend.src.core.database import get_db

    engine = create_async_engine(_get_real_url())
    Session = async_sessionmaker(engine, expire_on_commit=False)

    async def _override():
        async with Session() as session:
            yield session

    app.dependency_overrides[get_db] = _override

    def _cleanup_app():
        app.dependency_overrides.pop(get_db, None)

    return app, engine, _cleanup_app


# ── E2E #1: real Wazuh ransomware payload → case ──────────────────────


def test_e2e_real_ransomware_payload_creates_case():
    from backend.src.modules.integrations.application.jobs import (
        retry_pending_events_once,
    )

    payload = json.loads((FIXTURES / "ransomware_alert.json").read_text())
    body = json.dumps(payload).encode()
    secret = "e2e-secret-ransom"
    sig = _sign_hmac(body, secret)
    tenant_id = f"t-e2e-ransom-{uuid.uuid4().hex[:8]}"

    async def _go():
        app, app_engine, app_cleanup = _bind_app_to_real_db()
        eng, session = await _open_session()
        try:
            svc_id, pri_id, tax_id, _ = await _setup_common(
                session, tenant_id, payload,
            )
            source_id = await _seed_source_with_hmac(
                session, tenant_id=tenant_id,
                default_service_item_id=svc_id,
                default_priority_id=pri_id, secret=secret,
            )
            resp = await _post_webhook(app, source_id, body, sig)
            assert resp.status_code == 200, resp.text
            data = resp.json()["data"]
            assert data["status"] == "pending"
            inbound_id = data["inbound_event_id"]

            # Worker tick (in-test) — process the new pending event
            await retry_pending_events_once(session)

            from sqlalchemy import text as _t
            row = (await session.execute(_t(
                "SELECT c.case_type, c.title, c.case_number "
                "FROM cases c JOIN inbound_events ie ON ie.case_id = c.id "
                "WHERE ie.id = :iid"
            ), {"iid": inbound_id})).first()
            return row
        finally:
            await _cleanup_tenant(session, tenant_id)
            await session.close()
            await eng.dispose()
            app_cleanup()
            await app_engine.dispose()

    row = _run(_go())
    assert row is not None, "Case was not created from webhook"
    # case_type='incident' proves the taxonomy resolver fired (otherwise
    # we'd see the 'event' fallback for events without a taxonomy match).
    assert row[0] == "incident"
    assert row[1] == "Ransomware activity detected on host"
    assert row[2].startswith("INC-")


# ── E2E #2: duplicate webhook returns same case ───────────────────────


def test_e2e_duplicate_webhook_returns_duplicate_status():
    from backend.src.modules.integrations.application.jobs import (
        retry_pending_events_once,
    )

    payload = json.loads((FIXTURES / "brute_force.json").read_text())
    body = json.dumps(payload).encode()
    secret = "e2e-secret-bf"
    sig = _sign_hmac(body, secret)
    tenant_id = f"t-e2e-dup-{uuid.uuid4().hex[:8]}"

    async def _go():
        app, app_engine, app_cleanup = _bind_app_to_real_db()
        eng, session = await _open_session()
        try:
            svc_id, pri_id, _tax, _ = await _setup_common(
                session, tenant_id, payload,
            )
            source_id = await _seed_source_with_hmac(
                session, tenant_id=tenant_id,
                default_service_item_id=svc_id,
                default_priority_id=pri_id, secret=secret,
            )
            r1 = await _post_webhook(app, source_id, body, sig)
            assert r1.status_code == 200
            await retry_pending_events_once(session)

            r2 = await _post_webhook(app, source_id, body, sig)
            assert r2.status_code == 200
            return r1.json()["data"], r2.json()["data"]
        finally:
            await _cleanup_tenant(session, tenant_id)
            await session.close()
            await eng.dispose()
            app_cleanup()
            await app_engine.dispose()

    first, second = _run(_go())
    assert first["status"] == "pending"
    assert first["duplicate"] is False
    assert second["status"] == "duplicate"
    assert second["duplicate"] is True
    # Both deliveries point at the same inbound row
    assert second["inbound_event_id"] == first["inbound_event_id"]


# ── E2E #3: signature from wrong secret → 401 ─────────────────────────


def test_e2e_invalid_hmac_signature_rejected():
    """A signature from secret X cannot authenticate against source with secret Y."""
    payload = json.loads((FIXTURES / "brute_force.json").read_text())
    body = json.dumps(payload).encode()
    real_secret = "the-real-secret"
    wrong_secret = "what-attacker-guessed"
    wrong_sig = _sign_hmac(body, wrong_secret)
    tenant_id = f"t-e2e-iso-{uuid.uuid4().hex[:8]}"

    async def _go():
        app, app_engine, app_cleanup = _bind_app_to_real_db()
        eng, session = await _open_session()
        try:
            svc_id, pri_id, _tax, _ = await _setup_common(
                session, tenant_id, payload,
            )
            source_id = await _seed_source_with_hmac(
                session, tenant_id=tenant_id,
                default_service_item_id=svc_id,
                default_priority_id=pri_id, secret=real_secret,
            )
            return await _post_webhook(app, source_id, body, wrong_sig)
        finally:
            await _cleanup_tenant(session, tenant_id)
            await session.close()
            await eng.dispose()
            app_cleanup()
            await app_engine.dispose()

    resp = _run(_go())
    assert resp.status_code == 401, resp.text


# ── E2E #4: inactive source → 403 ─────────────────────────────────────


def test_e2e_inactive_source_returns_403():
    payload = json.loads((FIXTURES / "brute_force.json").read_text())
    body = json.dumps(payload).encode()
    secret = "e2e-inactive-secret"
    sig = _sign_hmac(body, secret)
    tenant_id = f"t-e2e-inactive-{uuid.uuid4().hex[:8]}"

    async def _go():
        app, app_engine, app_cleanup = _bind_app_to_real_db()
        eng, session = await _open_session()
        try:
            svc_id, pri_id, _tax, _ = await _setup_common(
                session, tenant_id, payload,
            )
            source_id = await _seed_source_with_hmac(
                session, tenant_id=tenant_id,
                default_service_item_id=svc_id,
                default_priority_id=pri_id, secret=secret,
            )
            # Deactivate the source AFTER creation so the auth_header_name
            # and secret are still loaded by the receiver
            from sqlalchemy import text as _t
            await session.execute(_t(
                "UPDATE integration_sources SET is_active = false "
                "WHERE id = :id"
            ), {"id": source_id})
            await session.commit()
            return await _post_webhook(app, source_id, body, sig)
        finally:
            await _cleanup_tenant(session, tenant_id)
            await session.close()
            await eng.dispose()
            app_cleanup()
            await app_engine.dispose()

    resp = _run(_go())
    assert resp.status_code == 403, resp.text
