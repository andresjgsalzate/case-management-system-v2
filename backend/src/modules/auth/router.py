"""Auth endpoints — Keycloak OIDC redirect flow (sub-spec 09 §3.6).

The browser hits ``GET /auth/login`` and gets redirected to Keycloak with
a PKCE challenge plus a signed state cookie. Keycloak sends the browser
back to ``GET /auth/callback?code=…&state=…`` where the backend redeems
the code, validates the access token, parks the refresh token in an
HttpOnly cookie, and bounces to the SPA with the access token in the URL
fragment (so it never lands in HTTP logs or proxy headers).

``GET /auth/logout`` reverses the flow: revoke the refresh token, clear
the cookie, redirect to Keycloak's end-session endpoint with a
``post_logout_redirect_uri`` back to the SPA login page.

``GET /auth/me`` still returns the CMS view of the current user (role +
permissions) so the frontend can populate its menus.
"""

from __future__ import annotations

import base64
import hashlib
import secrets
import time
from datetime import timedelta
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy import select

from backend.src.core.auth import get_keycloak_validator
from backend.src.core.config import get_settings
from backend.src.core.dependencies import DBSession
from backend.src.core.responses import SuccessResponse
from backend.src.modules.auth.keycloak_client import (
    KeycloakOAuthClient,
    build_authorize_url,
)
# Side-effect import: register `UserSessionModel` with the SQLAlchemy
# Base registry. Task 2.3 stopped using AuthUseCases (which previously
# pulled the model in transitively) so UserModel's `sessions` relationship
# would fail to resolve names at first mapper init without this line.
from backend.src.modules.auth.infrastructure import models as _auth_models  # noqa: F401


_bearer = HTTPBearer(auto_error=False)

router = APIRouter(prefix="/auth", tags=["auth"])

_STATE_COOKIE = "oidc_state"
_REFRESH_COOKIE = "cms_refresh"
_STATE_TTL_SECONDS = 600
_REFRESH_TTL_SECONDS = int(timedelta(days=7).total_seconds())


# ─── helpers ────────────────────────────────────────────────────────


def _pkce_pair() -> tuple[str, str]:
    """Return (verifier, challenge) for a PKCE S256 exchange."""
    verifier = secrets.token_urlsafe(64)
    challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
        .rstrip(b"=")
        .decode("ascii")
    )
    return verifier, challenge


def _encode_state_cookie(*, state: str, verifier: str, next_path: str) -> str:
    settings = get_settings()
    return jwt.encode(
        {
            "state": state,
            "verifier": verifier,
            "next": next_path,
            "exp": int(time.time()) + _STATE_TTL_SECONDS,
        },
        settings.SECRET_KEY,
        algorithm="HS256",
    )


def _decode_state_cookie(raw: str) -> dict:
    settings = get_settings()
    try:
        return jwt.decode(raw, settings.SECRET_KEY, algorithms=["HS256"])
    except JWTError as exc:
        raise HTTPException(400, "Invalid OIDC state cookie") from exc


def _backend_callback_url() -> str:
    s = get_settings()
    return f"{s.CMS_FRONTEND_URL.rstrip('/')}/api/v1/auth/callback"


def _oauth_client() -> KeycloakOAuthClient:
    s = get_settings()
    # `verify=False` because dev runs on a self-signed cert; in prod the
    # internal URL is plain HTTP within docker and the flag is moot.
    return KeycloakOAuthClient(
        issuer=s.KEYCLOAK_INTERNAL_URL,
        client_id=s.KEYCLOAK_FRONTEND_CLIENT_ID,
        verify_ssl=False,
    )


# ─── endpoints ──────────────────────────────────────────────────────


@router.get("/login")
async def auth_login(redirect_after: str = "/"):
    """Kick off the Authorization Code + PKCE flow.

    `redirect_after` is the SPA path the user lands on once login finishes
    (defaults to "/"). It's signed into the state cookie so the callback
    can honor it without trusting the URL.
    """
    settings = get_settings()
    state = secrets.token_urlsafe(32)
    verifier, challenge = _pkce_pair()

    # Open-redirect guard: only same-origin relative paths survive.
    next_path = redirect_after if redirect_after.startswith("/") else "/"

    auth_url = build_authorize_url(
        authorize_endpoint=(
            f"{settings.KEYCLOAK_ISSUER}/protocol/openid-connect/auth"
        ),
        client_id=settings.KEYCLOAK_FRONTEND_CLIENT_ID,
        redirect_uri=_backend_callback_url(),
        state=state,
        code_challenge=challenge,
    )

    response = RedirectResponse(auth_url, status_code=302)
    response.set_cookie(
        key=_STATE_COOKIE,
        value=_encode_state_cookie(
            state=state, verifier=verifier, next_path=next_path
        ),
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=_STATE_TTL_SECONDS,
        path="/api/v1/auth",
    )
    return response


@router.get("/callback")
async def auth_callback(code: str, state: str, request: Request):
    """Redeem the authorization code, validate the access token, hand off."""
    raw_cookie = request.cookies.get(_STATE_COOKIE)
    if not raw_cookie:
        raise HTTPException(400, "Missing OIDC state cookie")

    cookie_data = _decode_state_cookie(raw_cookie)
    if cookie_data.get("state") != state:
        raise HTTPException(400, "OIDC state mismatch")

    verifier = cookie_data["verifier"]
    next_path = cookie_data.get("next", "/")

    client = _oauth_client()
    try:
        tokens = await client.exchange_code(
            code=code,
            code_verifier=verifier,
            redirect_uri=_backend_callback_url(),
        )
    finally:
        await client.aclose()

    access_token = tokens["access_token"]
    refresh_token = tokens.get("refresh_token")
    expires_in = int(tokens.get("expires_in", 900))

    # Belt-and-braces: a token we just minted should validate locally.
    # Catches realm/audience misconfig before the SPA tries to use the token.
    validator = get_keycloak_validator()
    await validator.validate(access_token)

    settings = get_settings()
    landing = (
        f"{settings.CMS_FRONTEND_URL.rstrip('/')}{next_path}"
        f"#access_token={access_token}&expires_in={expires_in}"
    )
    response = RedirectResponse(landing, status_code=302)
    response.delete_cookie(_STATE_COOKIE, path="/api/v1/auth")
    if refresh_token:
        response.set_cookie(
            key=_REFRESH_COOKIE,
            value=refresh_token,
            httponly=True,
            secure=True,
            samesite="lax",
            max_age=_REFRESH_TTL_SECONDS,
            path="/api/v1/auth",
        )
    return response


@router.get("/logout")
async def auth_logout(request: Request):
    """Revoke the refresh token, clear cookies, hand off to Keycloak end-session."""
    settings = get_settings()
    refresh_token = request.cookies.get(_REFRESH_COOKIE)

    if refresh_token:
        client = _oauth_client()
        try:
            await client.revoke_refresh_token(refresh_token)
        finally:
            await client.aclose()

    landing = f"{settings.CMS_FRONTEND_URL.rstrip('/')}/login"
    end_session = (
        f"{settings.KEYCLOAK_ISSUER}/protocol/openid-connect/logout"
        f"?post_logout_redirect_uri={quote(landing, safe='')}"
        f"&client_id={settings.KEYCLOAK_FRONTEND_CLIENT_ID}"
    )
    response = RedirectResponse(end_session, status_code=302)
    response.delete_cookie(_REFRESH_COOKIE, path="/api/v1/auth")
    return response


@router.get("/me")
async def get_me(
    db: DBSession,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
):
    """Return the CMS view of the current user (role + permissions)."""
    if not credentials:
        raise HTTPException(status_code=401, detail="Not authenticated")

    validator = get_keycloak_validator()
    payload = await validator.validate(credentials.credentials)

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token")

    from backend.src.modules.roles.infrastructure.models import (
        PermissionModel,
        RoleModel,
    )
    from backend.src.modules.users.infrastructure.models import UserModel

    user = (
        await db.execute(select(UserModel).where(UserModel.id == user_id))
    ).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    role_name = None
    role_level = 1
    permissions: list[dict] = []
    if user.role_id:
        role = (
            await db.execute(select(RoleModel).where(RoleModel.id == user.role_id))
        ).scalar_one_or_none()
        if role:
            role_name = role.name
            role_level = getattr(role, "level", 1)
        perm_rows = (
            await db.execute(
                select(PermissionModel).where(PermissionModel.role_id == user.role_id)
            )
        ).scalars().all()
        permissions = [
            {"module": p.module, "action": p.action, "scope": p.scope}
            for p in perm_rows
        ]

    return SuccessResponse.ok(
        {
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "role_id": user.role_id,
            "role_name": role_name,
            "role_level": role_level,
            "permissions": permissions,
            "is_active": user.is_active,
            "avatar_url": getattr(user, "avatar_url", None),
            "email_notifications": getattr(user, "email_notifications", False),
            "created_at": user.created_at.isoformat() if user.created_at else "",
            "updated_at": user.updated_at.isoformat() if user.updated_at else "",
        }
    )
