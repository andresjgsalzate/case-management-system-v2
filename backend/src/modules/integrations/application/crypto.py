"""Fernet symmetric encryption for integration source secrets.

Secrets (HMAC keys, API tokens, bearer tokens) are stored encrypted at rest
in `integration_sources.auth_secret_encrypted`. The Fernet master key lives
in `INTEGRATIONS_ENCRYPTION_KEY` (env var, not in the DB).
"""
import secrets as _secrets

from cryptography.fernet import Fernet

from backend.src.core.config import get_settings


def _fernet() -> Fernet:
    key = get_settings().INTEGRATIONS_ENCRYPTION_KEY
    if not key:
        raise RuntimeError(
            "INTEGRATIONS_ENCRYPTION_KEY is not configured. "
            "Generate one via: python -c \"from cryptography.fernet import Fernet; "
            "print(Fernet.generate_key().decode())\""
        )
    return Fernet(key.encode("utf-8"))


def encrypt_secret(plaintext: str) -> str:
    return _fernet().encrypt(plaintext.encode("utf-8")).decode("utf-8")


def decrypt_secret(ciphertext: str) -> str:
    return _fernet().decrypt(ciphertext.encode("utf-8")).decode("utf-8")


def generate_secret(length: int = 64) -> str:
    """Generate a URL-safe random secret suitable for HMAC keys / API tokens."""
    return _secrets.token_urlsafe(length)
