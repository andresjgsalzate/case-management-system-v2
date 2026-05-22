"""Thin wrappers around Keycloak's OIDC + Admin REST APIs.

Two clients live here:

* ``KeycloakOAuthClient`` — performs the back-channel parts of the
  Authorization Code + PKCE dance used by the auth router (token
  exchange, refresh, end-session). The user-agent half (browser
  redirects) is built directly in `router.py` because that's where
  the FastAPI Response lives.

* ``KeycloakAdminClient`` — placeholder for the migration script
  (Task 2.4). Fills in user creation, role assignment, and
  password-reset triggers. Bare-minimum methods only; expand on
  demand rather than mirroring the entire Admin API.

Both clients accept an optional `httpx.AsyncClient` so tests can
stub the HTTP layer with `AsyncMock`.

Sub-spec 09 §3.5–§3.6.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import urlencode

import httpx


class KeycloakOAuthClient:
    """OIDC client used to redeem auth codes and revoke sessions."""

    def __init__(
        self,
        issuer: str,
        client_id: str,
        *,
        client_secret: str | None = None,
        http_client: httpx.AsyncClient | None = None,
        verify_ssl: bool = True,
    ) -> None:
        self.issuer = issuer.rstrip("/")
        self.client_id = client_id
        self.client_secret = client_secret
        self._http = http_client
        self._owns_http = http_client is None
        self._verify_ssl = verify_ssl

    @property
    def authorize_endpoint(self) -> str:
        return f"{self.issuer}/protocol/openid-connect/auth"

    @property
    def token_endpoint(self) -> str:
        return f"{self.issuer}/protocol/openid-connect/token"

    @property
    def end_session_endpoint(self) -> str:
        return f"{self.issuer}/protocol/openid-connect/logout"

    async def exchange_code(
        self,
        *,
        code: str,
        code_verifier: str,
        redirect_uri: str,
    ) -> dict[str, Any]:
        """Trade an authorization code for access/refresh tokens."""
        form = {
            "grant_type": "authorization_code",
            "client_id": self.client_id,
            "code": code,
            "code_verifier": code_verifier,
            "redirect_uri": redirect_uri,
        }
        if self.client_secret:
            form["client_secret"] = self.client_secret
        return await self._post_token(form)

    async def revoke_refresh_token(self, refresh_token: str) -> None:
        """End the Keycloak session attached to a refresh token."""
        form = {
            "client_id": self.client_id,
            "refresh_token": refresh_token,
        }
        if self.client_secret:
            form["client_secret"] = self.client_secret

        http = await self._ensure_http()
        # end-session endpoint returns 204 No Content when it accepts the call.
        # Don't raise_for_status — a 400 here typically means the session was
        # already gone, which is the desired outcome of "logout".
        await http.post(self.end_session_endpoint, data=form, timeout=5)

    async def aclose(self) -> None:
        if self._owns_http and self._http is not None:
            await self._http.aclose()
            self._http = None

    # ─── internals ──────────────────────────────────────────────────

    async def _post_token(self, form: dict[str, str]) -> dict[str, Any]:
        http = await self._ensure_http()
        response = await http.post(self.token_endpoint, data=form, timeout=5)
        response.raise_for_status()
        return response.json()

    async def _ensure_http(self) -> httpx.AsyncClient:
        if self._http is None:
            self._http = httpx.AsyncClient(verify=self._verify_ssl)
            self._owns_http = True
        return self._http


class KeycloakAdminClient:
    """Admin REST wrapper — populated by the user-migration script (Task 2.4).

    Authenticates via the client_credentials grant against the
    ``cms-backend`` confidential client declared in the realm export.
    """

    def __init__(
        self,
        server_url: str,
        realm: str,
        client_id: str,
        client_secret: str,
        *,
        http_client: httpx.AsyncClient | None = None,
        verify_ssl: bool = True,
    ) -> None:
        self.server_url = server_url.rstrip("/")
        self.realm = realm
        self.client_id = client_id
        self.client_secret = client_secret
        self._http = http_client
        self._owns_http = http_client is None
        self._verify_ssl = verify_ssl
        self._token: str | None = None

    @property
    def admin_base(self) -> str:
        return f"{self.server_url}/admin/realms/{self.realm}"

    @property
    def token_endpoint(self) -> str:
        return f"{self.server_url}/realms/{self.realm}/protocol/openid-connect/token"

    async def get_admin_token(self) -> str:
        """Cache-then-fetch service-account access token."""
        if self._token:
            return self._token

        form = {
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        }
        http = await self._ensure_http()
        response = await http.post(self.token_endpoint, data=form, timeout=5)
        response.raise_for_status()
        self._token = str(response.json()["access_token"])
        return self._token

    async def aclose(self) -> None:
        if self._owns_http and self._http is not None:
            await self._http.aclose()
            self._http = None

    async def _ensure_http(self) -> httpx.AsyncClient:
        if self._http is None:
            self._http = httpx.AsyncClient(verify=self._verify_ssl)
            self._owns_http = True
        return self._http


def build_authorize_url(
    *,
    authorize_endpoint: str,
    client_id: str,
    redirect_uri: str,
    state: str,
    code_challenge: str,
    scope: str = "openid profile email",
) -> str:
    """Compose the authorization URL the browser should be redirected to."""
    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": scope,
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }
    return f"{authorize_endpoint}?{urlencode(params)}"
