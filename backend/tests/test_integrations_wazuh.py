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
