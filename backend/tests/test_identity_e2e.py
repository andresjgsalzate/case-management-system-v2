"""
End-to-end integration tests for the identity system.

These tests require:
  1. PostgreSQL running and configured (DATABASE_URL in .env)
  2. Seed executed: python scripts/seed.py
  3. Environment variable: INTEGRATION_TESTS=1

Run with: INTEGRATION_TESTS=1 python -m pytest backend/tests/test_identity_e2e.py -v

Without INTEGRATION_TESTS=1, all tests are skipped automatically.
"""
import os
import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, patch


INTEGRATION = os.environ.get("INTEGRATION_TESTS") == "1"
skip_without_db = pytest.mark.skipif(
    not INTEGRATION,
    reason="Requires INTEGRATION_TESTS=1 and live PostgreSQL + seed"
)

ADMIN_EMAIL = "admin@cms.local"
ADMIN_PASSWORD = "ChangeMe123!"


@skip_without_db
@pytest.mark.asyncio
async def test_full_auth_flow():
    """Login → access protected endpoint → refresh → logout → verify token revoked."""
    from backend.src.main import create_app
    import backend.src.core.config as config_module
    import importlib
    importlib.reload(config_module)
    config_module.get_settings.cache_clear()

    app = create_app()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        # 1. Login
        login_res = await client.post("/api/v1/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD,
        })
        assert login_res.status_code == 200, f"Login failed: {login_res.text}"
        tokens = login_res.json()["data"]
        access_token = tokens["access_token"]
        refresh_token = tokens["refresh_token"]
        assert tokens["token_type"] == "bearer"

        # 2. Access protected endpoint
        roles_res = await client.get(
            "/api/v1/roles",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert roles_res.status_code == 200
        roles = roles_res.json()["data"]
        role_names = [r["name"] for r in roles]
        assert "Super Admin" in role_names
        assert "Agent" in role_names

        # 3. Refresh token (rotation)
        refresh_res = await client.post("/api/v1/auth/refresh", json={
            "refresh_token": refresh_token,
        })
        assert refresh_res.status_code == 200
        new_tokens = refresh_res.json()["data"]
        assert new_tokens["access_token"] != access_token
        assert new_tokens["refresh_token"] != refresh_token

        # 4. Old refresh token should now be revoked
        reuse_res = await client.post("/api/v1/auth/refresh", json={
            "refresh_token": refresh_token,
        })
        assert reuse_res.status_code == 401, "Old refresh token should be revoked after rotation"

        # 5. Logout with new token
        logout_res = await client.post("/api/v1/auth/logout", json={
            "refresh_token": new_tokens["refresh_token"],
        })
        assert logout_res.status_code == 204

        # 6. Verify new refresh token is also revoked after logout
        post_logout_res = await client.post("/api/v1/auth/refresh", json={
            "refresh_token": new_tokens["refresh_token"],
        })
        assert post_logout_res.status_code == 401, "Token should be revoked after logout"


@skip_without_db
@pytest.mark.asyncio
async def test_wrong_credentials_returns_401():
    """Login with wrong password returns 401."""
    from backend.src.main import create_app
    app = create_app()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        res = await client.post("/api/v1/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": "WrongPassword!",
        })
        assert res.status_code == 401
        assert res.json()["error"] == "UNAUTHORIZED"


@skip_without_db
@pytest.mark.asyncio
async def test_permission_denied_without_token():
    """Accessing protected endpoint without token returns 401."""
    from backend.src.main import create_app
    app = create_app()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        res = await client.get("/api/v1/roles")
        assert res.status_code in (401, 403)


@skip_without_db
@pytest.mark.asyncio
async def test_roles_seed_creates_four_roles():
    """Verify seed created exactly 4 roles."""
    from backend.src.main import create_app
    app = create_app()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        # Login first
        login_res = await client.post("/api/v1/auth/login", json={
            "email": ADMIN_EMAIL, "password": ADMIN_PASSWORD,
        })
        token = login_res.json()["data"]["access_token"]

        roles_res = await client.get(
            "/api/v1/roles",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert roles_res.status_code == 200
        roles = roles_res.json()["data"]
        role_names = {r["name"] for r in roles}
        assert role_names == {"Super Admin", "Admin", "Manager", "Agent"}
