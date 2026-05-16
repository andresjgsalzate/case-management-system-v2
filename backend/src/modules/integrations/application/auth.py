"""Auth validation per integration source.

Dispatches by `source.auth_method`:
- hmac:   verifies SHA256(secret, body) matches header value prefixed with "sha256="
- api_key: constant-time compares secret with header value
- bearer:  constant-time compares "Bearer <secret>" with header value
- none:    skips (not recommended for production sources)

All comparisons use `hmac.compare_digest` to prevent timing attacks.
Header lookup is case-insensitive (headers dict keys assumed already lower-cased
by the caller; HTTP frameworks normally provide this).
"""
import hashlib
import hmac

from backend.src.core.exceptions import BusinessRuleError, UnauthorizedError


_DEFAULT_HEADERS: dict[str, str] = {
    "hmac": "X-CMS-Signature",
    "api_key": "X-API-Key",
    "bearer": "Authorization",
}


def validate_auth(
    source,
    request_body: bytes,
    request_headers: dict,
    *,
    secret: str,
) -> None:
    """Validate `request` against `source`'s configured auth method.

    Raises UnauthorizedError on any auth failure.
    Raises BusinessRuleError on unknown auth_method (programmer error).
    """
    method = source.auth_method
    if method == "none":
        return

    header_name = (source.auth_header_name or _DEFAULT_HEADERS.get(method, "")).lower()
    provided = request_headers.get(header_name)
    if not provided:
        expected_name = source.auth_header_name or _DEFAULT_HEADERS.get(method, "")
        raise UnauthorizedError(f"Missing header {expected_name}")

    if method == "hmac":
        if not provided.startswith("sha256="):
            raise UnauthorizedError("HMAC signature format invalid")
        expected_hex = provided[len("sha256="):]
        computed = hmac.new(
            secret.encode("utf-8"), request_body, hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(computed, expected_hex):
            raise UnauthorizedError("HMAC signature mismatch")

    elif method == "api_key":
        if not hmac.compare_digest(secret, provided):
            raise UnauthorizedError("API key invalid")

    elif method == "bearer":
        expected = f"Bearer {secret}"
        if not hmac.compare_digest(expected, provided):
            raise UnauthorizedError("Bearer token invalid")

    else:
        raise BusinessRuleError(f"Unknown auth_method: {method}")
