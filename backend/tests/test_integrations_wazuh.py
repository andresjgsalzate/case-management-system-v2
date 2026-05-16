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
