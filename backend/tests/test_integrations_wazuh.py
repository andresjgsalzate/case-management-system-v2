"""Tests for Sub-spec 04 — Inbound Integrations & Wazuh Adapter."""
import os

import pytest

# Ensure a valid Fernet key is present BEFORE crypto module imports it via get_settings().
# Any valid urlsafe-base64 32-byte value works; this is a fixed test key only.
os.environ.setdefault(
    "INTEGRATIONS_ENCRYPTION_KEY",
    "Uf0yMQkQS7qc_AQVDGFYNc8Lc4E4l0QYtVkk4IZ5tXU=",
)


def test_models_import_smoke():
    """All 4 integrations models import without errors."""
    from backend.src.modules.integrations.infrastructure.models import (
        InboundEventModel,
        IntegrationMappingModel,
        IntegrationSourceModel,
        WazuhRuleTaxonomyMapModel,
    )
    assert IntegrationSourceModel.__tablename__ == "integration_sources"
    assert IntegrationMappingModel.__tablename__ == "integration_mappings"
    assert InboundEventModel.__tablename__ == "inbound_events"
    assert WazuhRuleTaxonomyMapModel.__tablename__ == "wazuh_rule_to_taxonomy_map"


# ── Task 2: Fernet crypto ──────────────────────────────────────────────


def test_encrypt_decrypt_roundtrip():
    """encrypt_secret then decrypt_secret returns the original plaintext."""
    from backend.src.modules.integrations.application.crypto import (
        decrypt_secret,
        encrypt_secret,
    )
    original = "my-hmac-secret-12345"
    encrypted = encrypt_secret(original)
    assert encrypted != original
    assert decrypt_secret(encrypted) == original


def test_encrypt_produces_different_ciphertexts_each_time():
    """Fernet uses random IV — same plaintext → different ciphertexts."""
    from backend.src.modules.integrations.application.crypto import encrypt_secret
    a = encrypt_secret("same")
    b = encrypt_secret("same")
    assert a != b


def test_decrypt_invalid_raises():
    """Garbage input raises InvalidToken — never silently returns wrong data."""
    from cryptography.fernet import InvalidToken
    from backend.src.modules.integrations.application.crypto import decrypt_secret
    with pytest.raises(InvalidToken):
        decrypt_secret("not-a-valid-encrypted-string")


def test_generate_secret_length_and_charset():
    """Generated secrets are urlsafe base64 with enough entropy."""
    from backend.src.modules.integrations.application.crypto import generate_secret
    s = generate_secret(length=32)
    assert len(s) >= 32  # urlsafe_token returns ~4/3 the byte length
    # urlsafe charset: A-Z, a-z, 0-9, -, _
    assert all(c.isalnum() or c in "-_" for c in s)


# ── Task 3: Auth validation ────────────────────────────────────────────


class _FakeSource:
    """Lightweight stand-in for IntegrationSourceModel used in auth tests."""
    def __init__(self, auth_method, auth_header_name=None):
        self.auth_method = auth_method
        self.auth_header_name = auth_header_name


def test_auth_none_method_skips_validation():
    """auth_method='none' returns without raising even with no headers."""
    from backend.src.modules.integrations.application.auth import validate_auth
    source = _FakeSource(auth_method="none")
    validate_auth(source, b'{}', {}, secret="ignored")  # no raise


def test_auth_missing_header_raises():
    from backend.src.modules.integrations.application.auth import validate_auth
    from backend.src.core.exceptions import UnauthorizedError
    source = _FakeSource(auth_method="api_key")
    with pytest.raises(UnauthorizedError):
        validate_auth(source, b'{}', {}, secret="abc")


def test_hmac_validation_correct_signature():
    import hashlib
    import hmac as _hmac
    from backend.src.modules.integrations.application.auth import validate_auth

    body = b'{"test": true}'
    secret = "test-secret"
    sig = _hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    headers = {"x-cms-signature": f"sha256={sig}"}
    source = _FakeSource(auth_method="hmac", auth_header_name="X-CMS-Signature")
    validate_auth(source, body, headers, secret=secret)  # no raise


def test_hmac_validation_wrong_signature():
    from backend.src.modules.integrations.application.auth import validate_auth
    from backend.src.core.exceptions import UnauthorizedError
    headers = {"x-cms-signature": "sha256=DEADBEEF"}
    source = _FakeSource(auth_method="hmac", auth_header_name="X-CMS-Signature")
    with pytest.raises(UnauthorizedError):
        validate_auth(source, b'{}', headers, secret="real-secret")


def test_hmac_validation_missing_sha256_prefix():
    from backend.src.modules.integrations.application.auth import validate_auth
    from backend.src.core.exceptions import UnauthorizedError
    headers = {"x-cms-signature": "abcdef"}  # missing "sha256=" prefix
    source = _FakeSource(auth_method="hmac", auth_header_name="X-CMS-Signature")
    with pytest.raises(UnauthorizedError):
        validate_auth(source, b'{}', headers, secret="x")


def test_api_key_validation_match():
    from backend.src.modules.integrations.application.auth import validate_auth
    source = _FakeSource(auth_method="api_key", auth_header_name="X-API-Key")
    validate_auth(source, b'{}', {"x-api-key": "the-key"}, secret="the-key")  # no raise


def test_api_key_validation_mismatch():
    from backend.src.modules.integrations.application.auth import validate_auth
    from backend.src.core.exceptions import UnauthorizedError
    source = _FakeSource(auth_method="api_key", auth_header_name="X-API-Key")
    with pytest.raises(UnauthorizedError):
        validate_auth(source, b'{}', {"x-api-key": "wrong"}, secret="the-key")


def test_bearer_validation_match():
    from backend.src.modules.integrations.application.auth import validate_auth
    source = _FakeSource(auth_method="bearer")  # default header: Authorization
    validate_auth(
        source, b'{}',
        {"authorization": "Bearer my-token"},
        secret="my-token",
    )  # no raise


def test_bearer_validation_mismatch():
    from backend.src.modules.integrations.application.auth import validate_auth
    from backend.src.core.exceptions import UnauthorizedError
    source = _FakeSource(auth_method="bearer")
    with pytest.raises(UnauthorizedError):
        validate_auth(
            source, b'{}',
            {"authorization": "Bearer wrong-token"},
            secret="my-token",
        )


def test_default_header_names_used_when_source_field_is_null():
    """If source.auth_header_name is None, defaults from _DEFAULT_HEADERS kick in."""
    from backend.src.modules.integrations.application.auth import validate_auth
    source = _FakeSource(auth_method="api_key", auth_header_name=None)
    validate_auth(source, b'{}', {"x-api-key": "k"}, secret="k")  # default 'X-API-Key'


# ── Task 4: Idempotency key + rate limiting ────────────────────────────


class _FakeIdSource:
    """Stand-in for IntegrationSourceModel exposing the fields needed by
    calculate_idempotency_key."""
    def __init__(self, id, source_type):
        self.id = id
        self.source_type = source_type


def test_idempotency_key_wazuh_is_deterministic():
    from backend.src.modules.integrations.application.idempotency import (
        calculate_idempotency_key,
    )
    source = _FakeIdSource(id="src-1", source_type="wazuh")
    payload = {
        "id": "1234.567", "rule": {"id": 87123},
        "agent": {"id": "001"}, "timestamp": "2026-01-01T00:00:00Z",
    }
    assert calculate_idempotency_key(source, payload) == calculate_idempotency_key(source, payload)


def test_idempotency_key_wazuh_ignores_irrelevant_payload_fields():
    """Two Wazuh events with the same canonical subset (id+rule+agent+ts) but
    different `full_log` text yield the same key — re-deliveries of the same
    alert should dedupe."""
    from backend.src.modules.integrations.application.idempotency import (
        calculate_idempotency_key,
    )
    source = _FakeIdSource(id="src-1", source_type="wazuh")
    base = {
        "id": "1234.567", "rule": {"id": 87123},
        "agent": {"id": "001"}, "timestamp": "2026-01-01T00:00:00Z",
    }
    p1 = {**base, "full_log": "first delivery"}
    p2 = {**base, "full_log": "second delivery with different text"}
    assert calculate_idempotency_key(source, p1) == calculate_idempotency_key(source, p2)


def test_idempotency_key_different_payloads_yield_different_keys():
    from backend.src.modules.integrations.application.idempotency import (
        calculate_idempotency_key,
    )
    source = _FakeIdSource(id="src-1", source_type="wazuh")
    p1 = {"id": "1234.567", "rule": {"id": 87123}, "agent": {"id": "001"}}
    p2 = {"id": "9999.000", "rule": {"id": 87123}, "agent": {"id": "001"}}
    assert calculate_idempotency_key(source, p1) != calculate_idempotency_key(source, p2)


def test_idempotency_key_includes_source_id():
    """Same payload, different source → different keys (so a Wazuh event seen
    by both prod and DR managers does not collide)."""
    from backend.src.modules.integrations.application.idempotency import (
        calculate_idempotency_key,
    )
    payload = {"id": "1.2", "rule": {"id": 100}, "agent": {"id": "001"}}
    src_a = _FakeIdSource(id="src-a", source_type="wazuh")
    src_b = _FakeIdSource(id="src-b", source_type="wazuh")
    assert calculate_idempotency_key(src_a, payload) != calculate_idempotency_key(src_b, payload)


def test_idempotency_key_generic_source_uses_full_payload():
    """Unknown source_type falls back to sha256 of the full payload."""
    from backend.src.modules.integrations.application.idempotency import (
        calculate_idempotency_key,
    )
    source = _FakeIdSource(id="s", source_type="custom")
    p1 = {"foo": "bar"}
    p2 = {"foo": "baz"}
    assert calculate_idempotency_key(source, p1) != calculate_idempotency_key(source, p2)


def test_rate_limit_allows_calls_under_limit():
    from backend.src.modules.integrations.application.idempotency import (
        check_rate_limit, reset_rate_limit_for_source,
    )
    reset_rate_limit_for_source("rl-under")
    for _ in range(5):
        check_rate_limit("rl-under", limit_per_minute=10)  # no raise


def test_rate_limit_raises_when_exceeded():
    from backend.src.modules.integrations.application.idempotency import (
        RateLimitExceededError, check_rate_limit, reset_rate_limit_for_source,
    )
    reset_rate_limit_for_source("rl-over")
    for _ in range(3):
        check_rate_limit("rl-over", limit_per_minute=3)
    with pytest.raises(RateLimitExceededError):
        check_rate_limit("rl-over", limit_per_minute=3)


def test_rate_limit_per_source_isolation():
    """Hitting the limit on source A does not affect source B."""
    from backend.src.modules.integrations.application.idempotency import (
        check_rate_limit, reset_rate_limit_for_source,
    )
    reset_rate_limit_for_source("rl-iso-a")
    reset_rate_limit_for_source("rl-iso-b")
    for _ in range(2):
        check_rate_limit("rl-iso-a", limit_per_minute=2)
    check_rate_limit("rl-iso-b", limit_per_minute=2)  # B still has full budget


# ── Task 5: Source CRUD + secret rotation ──────────────────────────────


import asyncio  # noqa: E402

import pytest as _pytest  # noqa: E402


def _run_db_query(async_query):
    """Run an async DB callable inline using the real DATABASE_URL.
    Mirrors the helper used in test_prioritization_engine.py."""
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from dotenv import dotenv_values

    env = dotenv_values("backend/.env")
    real_url = env.get("DATABASE_URL")
    if not real_url:
        _pytest.skip("DATABASE_URL not in backend/.env")

    async def _go():
        engine = create_async_engine(real_url)
        try:
            async with AsyncSession(engine, expire_on_commit=False) as session:
                return await async_query(session)
        finally:
            await engine.dispose()

    return asyncio.run(_go())


class _IntActor:
    """Stand-in for CurrentUser used in integrations use-case tests."""
    def __init__(self, user_id, role_name="Super Admin", tenant_id="t-int-test"):
        self.user_id = user_id
        # use_cases expect `.id` (created_by) AND `.role_id` / `.tenant_id`
        self.id = user_id
        self.role_name = role_name
        self.tenant_id = tenant_id
        self.role_id: str | None = None


async def _resolve_role_id(session, role_name):
    from sqlalchemy import text
    row = (await session.execute(text(
        "SELECT id FROM roles WHERE name = :n AND tenant_id IS NULL LIMIT 1"
    ), {"n": role_name})).first()
    return row[0] if row else None


async def _ensure_integrations_permission(session, role_id, action="manage"):
    """Idempotent INSERT of permissions row used until Task 14 seed lands."""
    from sqlalchemy import text
    import uuid as _uuid
    exists = (await session.execute(text(
        "SELECT 1 FROM permissions "
        "WHERE role_id = :r AND module = 'integrations' AND action = :a LIMIT 1"
    ), {"r": role_id, "a": action})).first()
    if exists:
        return
    await session.execute(text(
        "INSERT INTO permissions (id, role_id, module, action, scope) "
        "VALUES (:id, :r, 'integrations', :a, 'all')"
    ), {"id": str(_uuid.uuid4()), "r": role_id, "a": action})
    await session.commit()


def test_create_source_returns_plaintext_secret_distinct_from_db_value():
    from backend.src.modules.integrations.application.dtos import CreateSourcePayload
    from backend.src.modules.integrations.application.use_cases import (
        IntegrationsUseCases,
    )

    actor = _IntActor(user_id="ec35a91e-5778-4210-a631-c5ed673c679d")

    async def _setup_and_create(session):
        actor.role_id = await _resolve_role_id(session, actor.role_name)
        await _ensure_integrations_permission(session, actor.role_id)
        uc = IntegrationsUseCases(db=session)
        result = await uc.create_source(
            actor=actor,
            payload=CreateSourcePayload(
                tenant_id=actor.tenant_id,
                name="Wazuh test source",
                source_type="wazuh",
                auth_method="hmac",
            ),
        )
        # Cleanup
        from sqlalchemy import text
        await session.execute(text(
            "DELETE FROM integration_sources WHERE id = :id"
        ), {"id": result.source.id})
        await session.commit()
        return result

    result = _run_db_query(_setup_and_create)
    assert result.plaintext_secret  # non-empty
    # Source response must NOT echo the encrypted secret either
    assert not hasattr(result.source, "auth_secret_encrypted")
    assert result.source.source_type == "wazuh"
    assert result.source.auth_method == "hmac"


def test_create_source_default_secret_decrypts_back_to_plaintext():
    """The encrypted value persisted in DB roundtrips through decrypt_secret."""
    from sqlalchemy import text
    from backend.src.modules.integrations.application.crypto import decrypt_secret
    from backend.src.modules.integrations.application.dtos import CreateSourcePayload
    from backend.src.modules.integrations.application.use_cases import (
        IntegrationsUseCases,
    )

    actor = _IntActor(user_id="ec35a91e-5778-4210-a631-c5ed673c679d")

    async def _go(session):
        actor.role_id = await _resolve_role_id(session, actor.role_name)
        await _ensure_integrations_permission(session, actor.role_id)
        uc = IntegrationsUseCases(db=session)
        result = await uc.create_source(
            actor=actor,
            payload=CreateSourcePayload(
                tenant_id=actor.tenant_id, name="rt", source_type="custom",
                auth_method="api_key",
            ),
        )
        row = (await session.execute(text(
            "SELECT auth_secret_encrypted FROM integration_sources WHERE id = :id"
        ), {"id": result.source.id})).first()
        encrypted = row[0]
        plaintext = decrypt_secret(encrypted)
        # Cleanup
        await session.execute(text(
            "DELETE FROM integration_sources WHERE id = :id"
        ), {"id": result.source.id})
        await session.commit()
        return result.plaintext_secret, plaintext

    returned, decrypted = _run_db_query(_go)
    assert returned == decrypted


def test_rotate_secret_returns_new_and_invalidates_old():
    from sqlalchemy import text
    from backend.src.modules.integrations.application.crypto import decrypt_secret
    from backend.src.modules.integrations.application.dtos import CreateSourcePayload
    from backend.src.modules.integrations.application.use_cases import (
        IntegrationsUseCases,
    )

    actor = _IntActor(user_id="ec35a91e-5778-4210-a631-c5ed673c679d")

    async def _go(session):
        actor.role_id = await _resolve_role_id(session, actor.role_name)
        await _ensure_integrations_permission(session, actor.role_id)
        uc = IntegrationsUseCases(db=session)
        created = await uc.create_source(
            actor=actor,
            payload=CreateSourcePayload(
                tenant_id=actor.tenant_id, name="rot",
                source_type="wazuh", auth_method="hmac",
            ),
        )
        old_plaintext = created.plaintext_secret
        rotated = await uc.rotate_secret(actor=actor, source_id=created.source.id)
        # DB now holds the new secret
        row = (await session.execute(text(
            "SELECT auth_secret_encrypted FROM integration_sources WHERE id = :id"
        ), {"id": created.source.id})).first()
        new_plaintext_in_db = decrypt_secret(row[0])
        await session.execute(text(
            "DELETE FROM integration_sources WHERE id = :id"
        ), {"id": created.source.id})
        await session.commit()
        return old_plaintext, rotated.plaintext_secret, new_plaintext_in_db

    old, returned_new, db_new = _run_db_query(_go)
    assert old != returned_new
    assert returned_new == db_new


def test_create_source_denied_when_actor_lacks_permission():
    """Actor with role missing integrations:manage → PermissionDeniedError."""
    from backend.src.core.exceptions import PermissionDeniedError
    from backend.src.modules.integrations.application.dtos import CreateSourcePayload
    from backend.src.modules.integrations.application.use_cases import (
        IntegrationsUseCases,
    )

    # 'Reporter' role exists in seed but has no integrations:manage
    actor = _IntActor(
        user_id="ec35a91e-5778-4210-a631-c5ed673c679d",
        role_name="Reporter",
    )

    async def _go(session):
        actor.role_id = await _resolve_role_id(session, actor.role_name)
        # Defensive: drop any integrations:manage row that test runs may have inserted
        from sqlalchemy import text
        await session.execute(text(
            "DELETE FROM permissions "
            "WHERE role_id = :r AND module = 'integrations' AND action = 'manage'"
        ), {"r": actor.role_id})
        await session.commit()
        uc = IntegrationsUseCases(db=session)
        with _pytest.raises(PermissionDeniedError):
            await uc.create_source(
                actor=actor,
                payload=CreateSourcePayload(
                    tenant_id=actor.tenant_id, name="denied",
                    source_type="wazuh", auth_method="hmac",
                ),
            )

    _run_db_query(_go)


def test_update_source_changes_name_keeps_secret():
    from sqlalchemy import text
    from backend.src.modules.integrations.application.dtos import (
        CreateSourcePayload, UpdateSourcePayload,
    )
    from backend.src.modules.integrations.application.use_cases import (
        IntegrationsUseCases,
    )

    actor = _IntActor(user_id="ec35a91e-5778-4210-a631-c5ed673c679d")

    async def _go(session):
        actor.role_id = await _resolve_role_id(session, actor.role_name)
        await _ensure_integrations_permission(session, actor.role_id)
        uc = IntegrationsUseCases(db=session)
        created = await uc.create_source(
            actor=actor,
            payload=CreateSourcePayload(
                tenant_id=actor.tenant_id, name="old name",
                source_type="custom", auth_method="api_key",
            ),
        )
        original_encrypted = (await session.execute(text(
            "SELECT auth_secret_encrypted FROM integration_sources WHERE id = :id"
        ), {"id": created.source.id})).first()[0]

        updated = await uc.update_source(
            actor=actor, source_id=created.source.id,
            payload=UpdateSourcePayload(name="new name", is_active=False),
        )
        after_encrypted = (await session.execute(text(
            "SELECT auth_secret_encrypted FROM integration_sources WHERE id = :id"
        ), {"id": created.source.id})).first()[0]

        await session.execute(text(
            "DELETE FROM integration_sources WHERE id = :id"
        ), {"id": created.source.id})
        await session.commit()
        return updated, original_encrypted, after_encrypted

    updated, before, after = _run_db_query(_go)
    assert updated.name == "new name"
    assert updated.is_active is False
    assert before == after  # secret preserved


def test_list_sources_returns_tenant_scoped():
    from sqlalchemy import text
    from backend.src.modules.integrations.application.dtos import CreateSourcePayload
    from backend.src.modules.integrations.application.use_cases import (
        IntegrationsUseCases,
    )

    actor = _IntActor(
        user_id="ec35a91e-5778-4210-a631-c5ed673c679d",
        tenant_id="t-list-test",
    )

    async def _go(session):
        actor.role_id = await _resolve_role_id(session, actor.role_name)
        await _ensure_integrations_permission(session, actor.role_id)
        await _ensure_integrations_permission(session, actor.role_id, action="read")
        uc = IntegrationsUseCases(db=session)
        created = await uc.create_source(
            actor=actor,
            payload=CreateSourcePayload(
                tenant_id=actor.tenant_id, name="listed",
                source_type="wazuh", auth_method="hmac",
            ),
        )
        sources = await uc.list_sources(actor=actor)
        ids = {s.id for s in sources}
        await session.execute(text(
            "DELETE FROM integration_sources WHERE id = :id"
        ), {"id": created.source.id})
        await session.commit()
        return created.source.id, ids

    created_id, listed_ids = _run_db_query(_go)
    assert created_id in listed_ids


def test_get_source_not_found_raises():
    from backend.src.core.exceptions import NotFoundError
    from backend.src.modules.integrations.application.use_cases import (
        IntegrationsUseCases,
    )

    actor = _IntActor(user_id="ec35a91e-5778-4210-a631-c5ed673c679d")

    async def _go(session):
        actor.role_id = await _resolve_role_id(session, actor.role_name)
        await _ensure_integrations_permission(session, actor.role_id, action="read")
        uc = IntegrationsUseCases(db=session)
        with _pytest.raises(NotFoundError):
            await uc.get_source(actor=actor, source_id="00000000-0000-0000-0000-000000000000")

    _run_db_query(_go)


def test_delete_source_removes_when_no_events():
    from sqlalchemy import text
    from backend.src.modules.integrations.application.dtos import CreateSourcePayload
    from backend.src.modules.integrations.application.use_cases import (
        IntegrationsUseCases,
    )

    actor = _IntActor(user_id="ec35a91e-5778-4210-a631-c5ed673c679d")

    async def _go(session):
        actor.role_id = await _resolve_role_id(session, actor.role_name)
        await _ensure_integrations_permission(session, actor.role_id)
        uc = IntegrationsUseCases(db=session)
        created = await uc.create_source(
            actor=actor,
            payload=CreateSourcePayload(
                tenant_id=actor.tenant_id, name="todel",
                source_type="custom", auth_method="api_key",
            ),
        )
        await uc.delete_source(actor=actor, source_id=created.source.id)
        row = (await session.execute(text(
            "SELECT 1 FROM integration_sources WHERE id = :id"
        ), {"id": created.source.id})).first()
        return row

    row = _run_db_query(_go)
    assert row is None


# ── Task 6: Wazuh hardcoded parser ─────────────────────────────────────


class _ParserSource:
    """Minimal source stand-in for parser tests (parser only reads .id)."""
    def __init__(self, id="src-parser"):
        self.id = id


def _wazuh_payload_minimum():
    """Realistic Wazuh ransomware alert (trimmed)."""
    return {
        "id": "1700000000.123",
        "timestamp": "2026-05-16T10:00:00.000+0000",
        "rule": {
            "id": 87123, "level": 12,
            "groups": ["malware", "ransomware", "windows"],
            "description": "Ransomware activity detected on host",
            "firedtimes": 3,
        },
        "agent": {"id": "001", "name": "PC-FIN-04", "ip": "10.0.0.5"},
        "data": {
            "srcip": "1.2.3.4", "dstip": "10.0.0.5",
            "user": "jdoe", "process": "encryptor.exe",
            "file": "C:/temp/xyz.locked", "hash": "abc123def",
        },
        "full_log": "May 16 10:00:00 PC-FIN-04: ransomware payload executed",
    }


def test_wazuh_parser_extracts_basic_fields():
    from backend.src.modules.integrations.application.parsers.wazuh import (
        parse_wazuh,
    )
    event = parse_wazuh(_wazuh_payload_minimum(), source=_ParserSource())

    assert event.title == "Ransomware activity detected on host"
    assert event.wazuh_rule_id == 87123
    assert event.wazuh_level == 12
    assert event.wazuh_rule_groups == ["malware", "ransomware", "windows"]


def test_wazuh_parser_extracts_custom_values():
    from backend.src.modules.integrations.application.parsers.wazuh import (
        parse_wazuh,
    )
    event = parse_wazuh(_wazuh_payload_minimum(), source=_ParserSource())
    cv = event.custom_values

    assert cv["source_ip"] == "1.2.3.4"
    assert cv["destination_ip"] == "10.0.0.5"
    assert cv["affected_user"] == "jdoe"
    assert cv["process_name"] == "encryptor.exe"
    assert cv["file_path"] == "C:/temp/xyz.locked"
    assert cv["hash"] == "abc123def"
    assert cv["hostname"] == "PC-FIN-04"
    assert cv["host_ip"] == "10.0.0.5"
    assert cv["wazuh_level"] == "12"
    assert cv["wazuh_rule_id"] == "87123"
    assert cv["wazuh_rule_groups"] == "malware,ransomware,windows"
    assert cv["wazuh_agent_id"] == "001"
    assert cv["wazuh_firedtimes"] == "3"
    assert cv["wazuh_full_log"].startswith("May 16")


def test_wazuh_parser_omits_unset_optional_data_fields():
    """If `data` lacks srcip/dstuser, those keys are not in custom_values."""
    from backend.src.modules.integrations.application.parsers.wazuh import (
        parse_wazuh,
    )
    payload = _wazuh_payload_minimum()
    payload["data"] = {"user": "alice"}  # only `user`
    event = parse_wazuh(payload, source=_ParserSource())
    cv = event.custom_values
    assert cv["affected_user"] == "alice"
    assert "source_ip" not in cv
    assert "destination_ip" not in cv
    assert "file_path" not in cv


def test_wazuh_parser_handles_missing_data_section():
    """Payload without `data` doesn't crash; rule/agent extraction still works."""
    from backend.src.modules.integrations.application.parsers.wazuh import (
        parse_wazuh,
    )
    payload = _wazuh_payload_minimum()
    payload.pop("data")
    event = parse_wazuh(payload, source=_ParserSource())
    assert event.wazuh_rule_id == 87123
    assert "source_ip" not in event.custom_values
    assert event.custom_values["hostname"] == "PC-FIN-04"


def test_wazuh_parser_fallback_title_when_rule_description_missing():
    """`rule.description` missing → title 'Wazuh alert <rule_id>'."""
    from backend.src.modules.integrations.application.parsers.wazuh import (
        parse_wazuh,
    )
    payload = _wazuh_payload_minimum()
    payload["rule"].pop("description")
    event = parse_wazuh(payload, source=_ParserSource())
    assert event.title == "Wazuh alert 87123"


def test_wazuh_parser_truncates_title_to_500_chars():
    from backend.src.modules.integrations.application.parsers.wazuh import (
        parse_wazuh,
    )
    payload = _wazuh_payload_minimum()
    payload["rule"]["description"] = "X" * 600
    event = parse_wazuh(payload, source=_ParserSource())
    assert len(event.title) == 500


def test_wazuh_parser_truncates_full_log_to_5000_chars():
    """`full_log` can be enormous; capped to keep the case payload bounded."""
    from backend.src.modules.integrations.application.parsers.wazuh import (
        parse_wazuh,
    )
    payload = _wazuh_payload_minimum()
    payload["full_log"] = "Y" * 6000
    event = parse_wazuh(payload, source=_ParserSource())
    assert len(event.custom_values["wazuh_full_log"]) == 5000


def test_wazuh_parser_empty_rule_groups_yields_empty_string():
    from backend.src.modules.integrations.application.parsers.wazuh import (
        parse_wazuh,
    )
    payload = _wazuh_payload_minimum()
    payload["rule"]["groups"] = []
    event = parse_wazuh(payload, source=_ParserSource())
    assert event.custom_values["wazuh_rule_groups"] == ""
    assert event.wazuh_rule_groups == []


def test_normalized_event_dataclass_defaults():
    """NormalizedEvent fills empty defaults for non-Wazuh sources."""
    from backend.src.modules.integrations.application.parsers.normalized_event import (
        NormalizedEvent,
    )
    e = NormalizedEvent(title="t", description="d")
    assert e.custom_values == {}
    assert e.wazuh_rule_id is None
    assert e.wazuh_rule_groups == []
    assert e.wazuh_level is None


# ── Task 7: Generic JSONPath parser ────────────────────────────────────


class _Mapping:
    """Stand-in for IntegrationMappingModel rows passed to parse_via_mappings."""
    def __init__(
        self, target_field, json_path,
        transform=None, default_value=None, is_required=False,
    ):
        self.target_field = target_field
        self.json_path = json_path
        self.transform = transform
        self.default_value = default_value
        self.is_required = is_required


def _run_async(coro):
    """Tiny helper to call an async function from sync test bodies."""
    return asyncio.run(coro)


def test_generic_parser_extracts_title_via_jsonpath():
    from backend.src.modules.integrations.application.parsers.generic import (
        parse_via_mappings,
    )
    payload = {"event": {"name": "Custom alert", "id": "abc"}}
    mappings = [
        _Mapping(target_field="title", json_path="$.event.name", is_required=True),
    ]
    event = _run_async(parse_via_mappings(payload, mappings))
    assert event.title == "Custom alert"


def test_generic_parser_required_field_missing_raises_validation_error():
    from backend.src.core.exceptions import ValidationError
    from backend.src.modules.integrations.application.parsers.generic import (
        parse_via_mappings,
    )
    mappings = [
        _Mapping(target_field="title", json_path="$.missing.path", is_required=True),
    ]
    with _pytest.raises(ValidationError):
        _run_async(parse_via_mappings({"foo": "bar"}, mappings))


def test_generic_parser_optional_missing_falls_back_to_default_value():
    from backend.src.modules.integrations.application.parsers.generic import (
        parse_via_mappings,
    )
    mappings = [
        _Mapping(
            target_field="title", json_path="$.missing",
            default_value="DEFAULT TITLE",
        ),
    ]
    event = _run_async(parse_via_mappings({}, mappings))
    assert event.title == "DEFAULT TITLE"


def test_generic_parser_optional_missing_no_default_skips_field():
    """No match, no default, not required → field stays at NormalizedEvent default."""
    from backend.src.modules.integrations.application.parsers.generic import (
        parse_via_mappings,
    )
    mappings = [
        _Mapping(target_field="title", json_path="$.missing"),
    ]
    event = _run_async(parse_via_mappings({}, mappings))
    # Title falls back to NormalizedEvent's own default
    assert event.title == "Untitled event"


def test_generic_parser_uppercase_transform():
    from backend.src.modules.integrations.application.parsers.generic import (
        parse_via_mappings,
    )
    mappings = [
        _Mapping(target_field="title", json_path="$.x", transform="uppercase"),
    ]
    event = _run_async(parse_via_mappings({"x": "lower"}, mappings))
    assert event.title == "LOWER"


def test_generic_parser_truncate_transform_with_arg():
    from backend.src.modules.integrations.application.parsers.generic import (
        parse_via_mappings,
    )
    mappings = [
        _Mapping(target_field="title", json_path="$.x", transform="truncate(5)"),
    ]
    event = _run_async(parse_via_mappings({"x": "abcdefghij"}, mappings))
    assert event.title == "abcde"


def test_generic_parser_regex_transform_extracts_match():
    from backend.src.modules.integrations.application.parsers.generic import (
        parse_via_mappings,
    )
    mappings = [
        _Mapping(
            target_field="title", json_path="$.x",
            transform=r"regex:CVE-\d{4}-\d+",
        ),
    ]
    event = _run_async(parse_via_mappings(
        {"x": "Patch fixes CVE-2026-12345 in OpenSSL"}, mappings,
    ))
    assert event.title == "CVE-2026-12345"


def test_generic_parser_custom_prefix_routes_to_custom_values():
    """target_field='custom.affected_user' → custom_values['affected_user']."""
    from backend.src.modules.integrations.application.parsers.generic import (
        parse_via_mappings,
    )
    mappings = [
        _Mapping(
            target_field="custom.affected_user",
            json_path="$.user", is_required=True,
        ),
    ]
    event = _run_async(parse_via_mappings({"user": "alice"}, mappings))
    assert event.custom_values["affected_user"] == "alice"


def test_generic_parser_unknown_transform_passes_value_through():
    """Unknown transform name silently no-ops rather than crashing the pipeline."""
    from backend.src.modules.integrations.application.parsers.generic import (
        parse_via_mappings,
    )
    mappings = [
        _Mapping(
            target_field="title", json_path="$.x",
            transform="nonexistent_transform",
        ),
    ]
    event = _run_async(parse_via_mappings({"x": "raw"}, mappings))
    assert event.title == "raw"


def test_generic_parser_title_truncated_to_500_chars():
    from backend.src.modules.integrations.application.parsers.generic import (
        parse_via_mappings,
    )
    mappings = [
        _Mapping(target_field="title", json_path="$.x", is_required=True),
    ]
    event = _run_async(parse_via_mappings({"x": "Y" * 600}, mappings))
    assert len(event.title) == 500
