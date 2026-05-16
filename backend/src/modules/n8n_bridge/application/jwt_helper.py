"""Short-lived JWT for n8n → CMS callbacks (second-level auth alongside HMAC).

When CMS triggers an n8n workflow it issues a JWT bound to the case_id and
mints it with a TTL covering the expected playbook runtime. n8n echoes the
JWT in every callback header; CMS validates both the HMAC signature AND the
JWT. Defense in depth: even if the HMAC secret leaks, the JWT scoping by
case_id limits what an attacker can mutate.
"""
from datetime import datetime, timedelta, timezone

import jwt

from backend.src.core.config import get_settings
from backend.src.core.exceptions import UnauthorizedError


ALGORITHM = "HS256"
ISSUER = "cms"
AUDIENCE = "n8n-callback"


def _secret() -> str:
    s = get_settings()
    secret = getattr(s, "N8N_CALLBACK_JWT_SECRET", None) or s.SECRET_KEY
    if not secret:
        raise RuntimeError(
            "N8N_CALLBACK_JWT_SECRET (or SECRET_KEY) must be configured",
        )
    return secret


def issue_callback_jwt(*, case_id: str, ttl_seconds: int = 3600) -> str:
    """Issue a JWT for n8n to echo in callbacks for `case_id`.

    Negative `ttl_seconds` produces an already-expired token (useful for tests
    that need to assert validation rejects expired tokens deterministically).
    """
    now = datetime.now(timezone.utc)
    payload = {
        "iss": ISSUER,
        "aud": AUDIENCE,
        "sub": "n8n",
        "iat": now,
        "exp": now + timedelta(seconds=ttl_seconds),
        "case_id": case_id,
    }
    return jwt.encode(payload, _secret(), algorithm=ALGORITHM)


def validate_callback_jwt(
    token: str, *, expected_case_id: str | None = None,
) -> dict:
    """Decode and verify the JWT. Raises UnauthorizedError on any failure.

    When `expected_case_id` is provided, the claim must match — protects
    against cross-case token re-use. Pass None when the case_id comes from
    a trusted source (URL path validated separately).
    """
    try:
        claims = jwt.decode(
            token, _secret(), algorithms=[ALGORITHM],
            audience=AUDIENCE, issuer=ISSUER,
        )
    except jwt.ExpiredSignatureError:
        raise UnauthorizedError("Callback JWT expired")
    except jwt.InvalidTokenError as e:
        raise UnauthorizedError(f"Callback JWT invalid: {e}")

    if expected_case_id is not None and claims.get("case_id") != expected_case_id:
        raise UnauthorizedError("Callback JWT case_id mismatch")
    return claims
