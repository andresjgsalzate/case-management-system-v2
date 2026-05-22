"""Authentication primitives — Keycloak token validation (sub-spec 09)."""

from functools import lru_cache

from backend.src.core.auth.keycloak import KeycloakTokenValidator
from backend.src.core.config import get_settings


@lru_cache
def get_keycloak_validator() -> KeycloakTokenValidator:
    """Process-wide validator instance.

    Wrapped in `lru_cache` so the JWKS cache and the underlying httpx client
    are shared across requests. Tests override this via monkeypatch on the
    module that imports it (e.g. `permission_checker.get_keycloak_validator`).
    """
    settings = get_settings()
    return KeycloakTokenValidator(
        jwks_url=settings.KEYCLOAK_JWKS_URL,
        audience=settings.KEYCLOAK_AUDIENCE,
        issuer=settings.KEYCLOAK_ISSUER,
    )


__all__ = ["KeycloakTokenValidator", "get_keycloak_validator"]
