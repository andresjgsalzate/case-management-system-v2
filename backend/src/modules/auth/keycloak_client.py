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
    """Admin REST wrapper used by the user-migration script (Task 2.4).

    Two authentication modes:

    * Service account via the ``cms-backend`` confidential client
      (``client_credentials`` grant). Lighter footprint, requires the
      service account to be granted ``realm-management`` roles.
    * Master-realm bootstrap admin via the ``admin-cli`` client
      (``password`` grant). Heavier privileges, used by the
      migration script which needs full user-creation rights.

    Prefer ``from_admin_password`` for one-off scripts and the default
    constructor for long-running back-end code.
    """

    def __init__(
        self,
        server_url: str,
        realm: str,
        client_id: str,
        client_secret: str | None = None,
        *,
        admin_user: str | None = None,
        admin_password: str | None = None,
        http_client: httpx.AsyncClient | None = None,
        verify_ssl: bool = True,
    ) -> None:
        self.server_url = server_url.rstrip("/")
        self.realm = realm
        self.client_id = client_id
        self.client_secret = client_secret
        self.admin_user = admin_user
        self.admin_password = admin_password
        self._http = http_client
        self._owns_http = http_client is None
        self._verify_ssl = verify_ssl
        self._token: str | None = None

    # ─── factories ──────────────────────────────────────────────

    @classmethod
    def from_admin_password(
        cls,
        *,
        server_url: str,
        realm: str,
        admin_user: str,
        admin_password: str,
        http_client: httpx.AsyncClient | None = None,
        verify_ssl: bool = True,
    ) -> "KeycloakAdminClient":
        return cls(
            server_url=server_url,
            realm=realm,
            client_id="admin-cli",
            admin_user=admin_user,
            admin_password=admin_password,
            http_client=http_client,
            verify_ssl=verify_ssl,
        )

    # ─── URL helpers ────────────────────────────────────────────

    @property
    def admin_base(self) -> str:
        return f"{self.server_url}/admin/realms/{self.realm}"

    @property
    def master_token_endpoint(self) -> str:
        return (
            f"{self.server_url}/realms/master/protocol/openid-connect/token"
        )

    @property
    def realm_token_endpoint(self) -> str:
        return (
            f"{self.server_url}/realms/{self.realm}"
            "/protocol/openid-connect/token"
        )

    # ─── token + admin operations ───────────────────────────────

    async def get_admin_token(self) -> str:
        """Cache-then-fetch an admin access token."""
        if self._token:
            return self._token

        http = await self._ensure_http()
        if self.admin_user and self.admin_password:
            # Master-realm password grant (bootstrap admin path).
            form = {
                "grant_type": "password",
                "client_id": "admin-cli",
                "username": self.admin_user,
                "password": self.admin_password,
            }
            response = await http.post(
                self.master_token_endpoint, data=form, timeout=10
            )
        else:
            # Service-account path (cms-backend confidential client).
            assert self.client_secret, (
                "client_secret required when admin credentials are absent"
            )
            form = {
                "grant_type": "client_credentials",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
            }
            response = await http.post(
                self.realm_token_endpoint, data=form, timeout=10
            )

        response.raise_for_status()
        self._token = str(response.json()["access_token"])
        return self._token

    async def list_realm_roles(self) -> list[dict[str, Any]]:
        """Return all realm roles in the target realm."""
        headers = await self._auth_headers()
        http = await self._ensure_http()
        response = await http.get(
            f"{self.admin_base}/roles", headers=headers, timeout=10
        )
        response.raise_for_status()
        roles: list[dict[str, Any]] = response.json()
        return roles

    async def create_user(self, payload: dict[str, Any]) -> str:
        """Provision a new user; returns the Keycloak user id.

        Keycloak's create endpoint returns 201 with a `Location` header
        of the form `/admin/realms/{realm}/users/{id}`. If the realm
        accepts the ``id`` field on POST (newer versions do), the
        returned id will match `payload["id"]`.
        """
        headers = await self._auth_headers()
        http = await self._ensure_http()
        response = await http.post(
            f"{self.admin_base}/users",
            json=payload,
            headers=headers,
            timeout=15,
        )
        response.raise_for_status()
        location = response.headers.get("location", "")
        return location.rstrip("/").rsplit("/", 1)[-1] or str(payload.get("id", ""))

    async def assign_realm_roles(
        self, user_id: str, roles: list[dict[str, Any]]
    ) -> None:
        """Assign realm roles to an existing user."""
        headers = await self._auth_headers()
        http = await self._ensure_http()
        response = await http.post(
            f"{self.admin_base}/users/{user_id}/role-mappings/realm",
            json=roles,
            headers=headers,
            timeout=10,
        )
        response.raise_for_status()

    async def send_password_reset(
        self, user_id: str, *, lifespan_seconds: int = 86400
    ) -> None:
        """Trigger Keycloak's ``UPDATE_PASSWORD`` required-action email."""
        headers = await self._auth_headers()
        http = await self._ensure_http()
        response = await http.put(
            f"{self.admin_base}/users/{user_id}/execute-actions-email",
            params={"lifespan": lifespan_seconds},
            json=["UPDATE_PASSWORD"],
            headers=headers,
            timeout=15,
        )
        response.raise_for_status()

    async def aclose(self) -> None:
        if self._owns_http and self._http is not None:
            await self._http.aclose()
            self._http = None

    # ─── internals ──────────────────────────────────────────────

    async def _auth_headers(self) -> dict[str, str]:
        token = await self.get_admin_token()
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

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
