"""Unit tests for the Keycloak token validator (sub-spec 09, Task 2.1).

These mock the JWKS HTTP fetch with a fresh RSA key pair per test so the
validator never needs a running Keycloak. Production wires `httpx.AsyncClient`
in by default; the test injects an AsyncMock.
"""

import time
from unittest.mock import AsyncMock, MagicMock

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.rsa import generate_private_key
from jose import jwt
from jose.utils import long_to_base64

from backend.src.core.auth.keycloak import KeycloakTokenValidator
from backend.src.core.exceptions import UnauthorizedError


ISSUER = "https://cms.local/auth/realms/cms"
AUDIENCE = "cms-frontend"
KID = "test-kid"


def _public_jwk(rsa_key, kid: str = KID) -> dict:
    """Turn an RSA public key into a Keycloak-shaped JWK dict."""
    nums = rsa_key.public_key().public_numbers()
    return {
        "kty": "RSA",
        "kid": kid,
        "use": "sig",
        "alg": "RS256",
        "n": long_to_base64(nums.n).decode("ascii"),
        "e": long_to_base64(nums.e).decode("ascii"),
    }


def _sign(claims: dict, rsa_key, kid: str = KID) -> str:
    """Sign a JWT with the given RSA private key."""
    pem = rsa_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    return jwt.encode(claims, pem.decode(), algorithm="RS256", headers={"kid": kid})


def _baseline_claims() -> dict:
    now = int(time.time())
    return {
        "sub": "abc-123",
        "iss": ISSUER,
        "aud": AUDIENCE,
        "exp": now + 300,
        "iat": now,
        "email": "user@example.com",
        "realm_access": {"roles": ["admin"]},
    }


def _validator_with_jwks(jwks_dict: dict) -> KeycloakTokenValidator:
    """Build a validator whose HTTP client always returns `jwks_dict`."""
    response = MagicMock()
    response.json = MagicMock(return_value=jwks_dict)
    response.raise_for_status = MagicMock(return_value=None)
    http = AsyncMock()
    http.get = AsyncMock(return_value=response)
    return KeycloakTokenValidator(
        jwks_url="http://test/jwks",
        audience=AUDIENCE,
        issuer=ISSUER,
        http_client=http,
    )


@pytest.fixture
def rsa_key():
    return generate_private_key(public_exponent=65537, key_size=2048)


async def test_validator_rejects_expired_token(rsa_key):
    validator = _validator_with_jwks({"keys": [_public_jwk(rsa_key)]})
    claims = _baseline_claims()
    claims["exp"] = int(time.time()) - 60   # one minute in the past
    token = _sign(claims, rsa_key)

    with pytest.raises(UnauthorizedError):
        await validator.validate(token)


async def test_validator_rejects_wrong_audience(rsa_key):
    validator = _validator_with_jwks({"keys": [_public_jwk(rsa_key)]})
    claims = _baseline_claims()
    claims["aud"] = "some-other-client"
    token = _sign(claims, rsa_key)

    with pytest.raises(UnauthorizedError):
        await validator.validate(token)


async def test_validator_rejects_invalid_signature(rsa_key):
    # JWKS publishes `rsa_key`, but the token is signed by `intruder_key`.
    intruder_key = generate_private_key(public_exponent=65537, key_size=2048)
    validator = _validator_with_jwks({"keys": [_public_jwk(rsa_key)]})
    token = _sign(_baseline_claims(), intruder_key)

    with pytest.raises(UnauthorizedError):
        await validator.validate(token)


async def test_validator_extracts_roles_from_realm_access(rsa_key):
    validator = _validator_with_jwks({"keys": [_public_jwk(rsa_key)]})
    claims = _baseline_claims()
    claims["realm_access"] = {"roles": ["super_admin", "admin"]}
    token = _sign(claims, rsa_key)

    payload = await validator.validate(token)

    assert payload["sub"] == "abc-123"
    assert payload["email"] == "user@example.com"
    assert payload["realm_access"]["roles"] == ["super_admin", "admin"]


# ─────────────────────────────────────────────────────────────
#  Task 2.2 — PermissionChecker accepts Keycloak-validated tokens
# ─────────────────────────────────────────────────────────────

from fastapi.security import HTTPAuthorizationCredentials


def _mock_db_session(role, permission, team_id=None):
    """AsyncSession stub that returns the given role/permission/team_id
    in the order PermissionChecker queries them."""
    role_result = MagicMock()
    role_result.scalar_one_or_none = MagicMock(return_value=role)

    perm_result = MagicMock()
    perm_result.scalar_one_or_none = MagicMock(return_value=permission)

    team_result = MagicMock()
    team_result.scalar_one_or_none = MagicMock(return_value=team_id)

    db = AsyncMock()
    db.execute = AsyncMock(side_effect=[role_result, perm_result, team_result])
    return db


async def test_permission_checker_accepts_keycloak_token(monkeypatch):
    """PermissionChecker must build CurrentUser from a Keycloak-validated
    payload, resolving the highest-level realm role into a CMS role_id."""
    from backend.src.core.middleware import permission_checker as pc_module
    from backend.src.core.middleware.permission_checker import (
        PermissionChecker, CurrentUser,
    )

    fake_validator = AsyncMock()
    fake_validator.validate = AsyncMock(return_value={
        "sub": "user-123",
        "email": "alice@example.com",
        "tenant_id": "tenant-A",
        "realm_access": {"roles": ["admin", "agent"]},
    })
    monkeypatch.setattr(
        pc_module, "get_keycloak_validator", lambda: fake_validator
    )
    # Silence the audit-actor side effect — module under test imports it lazily.
    monkeypatch.setattr(
        "backend.src.modules.audit.application.middleware.set_current_actor",
        lambda _u: None,
    )

    fake_role = MagicMock(
        id="role-admin-uuid", level=5, is_global=False, name="admin",
    )
    fake_perm = MagicMock(
        scope="tenant", role_id="role-admin-uuid",
        module="cases", action="read",
    )
    db = _mock_db_session(fake_role, fake_perm, team_id=None)

    creds = HTTPAuthorizationCredentials(
        scheme="Bearer", credentials="some.keycloak.jwt"
    )
    checker = PermissionChecker(module="cases", action="read")

    current = await checker(credentials=creds, db=db)

    assert isinstance(current, CurrentUser)
    assert current.user_id == "user-123"
    assert current.email == "alice@example.com"
    assert current.tenant_id == "tenant-A"
    assert current.role_id == "role-admin-uuid"
    assert current.role_level == 5
    assert current.scope == "tenant"
    fake_validator.validate.assert_awaited_once_with("some.keycloak.jwt")


# ─────────────────────────────────────────────────────────────
#  Task 2.3 — Backend auth router redirects to Keycloak
# ─────────────────────────────────────────────────────────────


async def test_login_redirects_to_keycloak(client):
    """GET /auth/login should issue a 302/307 redirect to the Keycloak
    authorization endpoint with PKCE parameters and a signed state cookie."""
    response = await client.get("/api/v1/auth/login", follow_redirects=False)

    assert response.status_code in (302, 307)

    location = response.headers.get("location", "")
    assert "/auth/realms/cms/protocol/openid-connect/auth" in location
    assert "client_id=cms-frontend" in location
    assert "response_type=code" in location
    assert "code_challenge=" in location
    assert "code_challenge_method=S256" in location
    assert "state=" in location

    # Signed state cookie carries the PKCE verifier across to /callback.
    raw_cookies = response.headers.get("set-cookie", "")
    assert "oidc_state=" in raw_cookies


# ─────────────────────────────────────────────────────────────
#  Task 2.4 — User migration helpers
# ─────────────────────────────────────────────────────────────


def test_split_full_name_two_parts():
    from backend.scripts.migrate_users_to_keycloak import split_full_name
    assert split_full_name("Alice Smith") == ("Alice", "Smith")


def test_split_full_name_single():
    from backend.scripts.migrate_users_to_keycloak import split_full_name
    assert split_full_name("Cher") == ("Cher", "")


def test_split_full_name_multi_word_lastname():
    from backend.scripts.migrate_users_to_keycloak import split_full_name
    assert split_full_name("Maria del Pilar Lopez") == (
        "Maria",
        "del Pilar Lopez",
    )


def test_build_user_payload_maps_fields():
    from backend.scripts.migrate_users_to_keycloak import build_user_payload

    user = MagicMock(
        id="user-uuid-1",
        email="alice@example.com",
        full_name="Alice Smith",
        is_active=True,
        tenant_id="tenant-a",
    )
    payload = build_user_payload(user)

    assert payload["id"] == "user-uuid-1"
    assert payload["username"] == "alice@example.com"
    assert payload["email"] == "alice@example.com"
    assert payload["firstName"] == "Alice"
    assert payload["lastName"] == "Smith"
    assert payload["enabled"] is True
    assert payload["emailVerified"] is True
    assert payload["attributes"]["tenant_id"] == ["tenant-a"]


def test_build_user_payload_defaults_tenant_when_null():
    from backend.scripts.migrate_users_to_keycloak import build_user_payload

    user = MagicMock(
        id="u2",
        email="b@x.com",
        full_name="Bob",
        is_active=False,
        tenant_id=None,
    )
    payload = build_user_payload(user)

    assert payload["enabled"] is False
    assert payload["attributes"]["tenant_id"] == ["default"]
    assert payload["lastName"] == ""
