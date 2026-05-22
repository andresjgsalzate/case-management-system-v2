"""Keycloak OIDC token validator.

Validates RS256-signed JWTs against the Keycloak realm's JWKS endpoint.
Designed to drop into `PermissionChecker` (Task 2.2) without changing
its caller-facing signature — the validator only produces a verified
claims dict; mapping claims into the `CurrentUser` happens upstream.

Sub-spec 09 §3.5.
"""

from __future__ import annotations

import time
from typing import Any

import httpx
from jose import JWTError, jwt

from backend.src.core.exceptions import UnauthorizedError


class KeycloakTokenValidator:
    """Verify RS256 JWTs minted by Keycloak.

    JWKS is cached in-process for `jwks_ttl_seconds` (default 1 h). On a
    `kid` cache miss we force one refresh before giving up — this covers
    a key rotation that lands mid-TTL without an extra round-trip on the
    happy path.

    The HTTP client is injectable so unit tests can stub the JWKS
    response without a network call. In production the validator owns
    a lazily-created `httpx.AsyncClient`.
    """

    def __init__(
        self,
        jwks_url: str,
        audience: str,
        issuer: str,
        *,
        http_client: httpx.AsyncClient | None = None,
        jwks_ttl_seconds: int = 3600,
    ) -> None:
        self.jwks_url = jwks_url
        self.audience = audience
        self.issuer = issuer
        self._http: httpx.AsyncClient | None = http_client
        self._owns_http = http_client is None
        self._ttl = jwks_ttl_seconds
        self._cache: dict[str, Any] | None = None
        self._cache_ts: float = 0.0

    async def validate(self, token: str) -> dict[str, Any]:
        try:
            header = jwt.get_unverified_header(token)
            kid = header.get("kid")
            if not kid:
                raise UnauthorizedError("Token missing 'kid' header")

            key = await self._get_signing_key(kid)

            return jwt.decode(
                token,
                key,
                algorithms=["RS256"],
                audience=self.audience,
                issuer=self.issuer,
            )
        except JWTError as exc:
            # python-jose raises the same base for every claim failure
            # (signature, exp, aud, iss). Collapse them into the CMS
            # exception type — callers shouldn't depend on jose internals.
            raise UnauthorizedError(f"Invalid Keycloak token: {exc}") from exc
        except httpx.HTTPError as exc:
            # JWKS endpoint unreachable / 5xx — fail closed.
            raise UnauthorizedError(
                f"Cannot fetch Keycloak signing keys: {exc}"
            ) from exc

    async def aclose(self) -> None:
        """Release the owned HTTP client. No-op if one was injected."""
        if self._owns_http and self._http is not None:
            await self._http.aclose()
            self._http = None

    # ─── internals ──────────────────────────────────────────────────

    async def _get_signing_key(self, kid: str) -> dict[str, Any]:
        jwks = await self._fetch_jwks(force_refresh=False)
        key = self._find_key(jwks, kid)
        if key is not None:
            return key

        # `kid` not in the cached set — could be a rotation. Force one
        # refresh, then give up.
        jwks = await self._fetch_jwks(force_refresh=True)
        key = self._find_key(jwks, kid)
        if key is None:
            raise UnauthorizedError(f"Unknown signing key id: {kid}")
        return key

    @staticmethod
    def _find_key(jwks: dict[str, Any], kid: str) -> dict[str, Any] | None:
        for k in jwks.get("keys", []):
            if k.get("kid") == kid:
                return k
        return None

    async def _fetch_jwks(self, *, force_refresh: bool) -> dict[str, Any]:
        now = time.time()
        if (
            not force_refresh
            and self._cache is not None
            and (now - self._cache_ts) < self._ttl
        ):
            return self._cache

        http = await self._ensure_http()
        response = await http.get(self.jwks_url, timeout=5)
        response.raise_for_status()
        jwks: dict[str, Any] = response.json()
        self._cache = jwks
        self._cache_ts = now
        return jwks

    async def _ensure_http(self) -> httpx.AsyncClient:
        if self._http is None:
            self._http = httpx.AsyncClient()
            self._owns_http = True
        return self._http
