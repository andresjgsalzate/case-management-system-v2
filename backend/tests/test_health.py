import pytest


@pytest.mark.asyncio
async def test_health_endpoint(client):
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["data"]["status"] == "ok"


@pytest.mark.asyncio
async def test_app_error_handler_returns_json(client):
    from fastapi import APIRouter
    from backend.src.core.exceptions import NotFoundError

    # Verify the exception handler maps correctly
    from backend.src.main import create_app
    import importlib, os
    from unittest.mock import patch, AsyncMock

    env = {
        "DATABASE_URL": "postgresql+asyncpg://user:pass@localhost/db",
        "REDIS_URL": "redis://localhost:6379/0",
        "SECRET_KEY": "test-secret-key-for-unit-tests-only-32ch",
    }
    with patch.dict(os.environ, env, clear=False):
        import backend.src.core.config as config_module
        importlib.reload(config_module)
        config_module.get_settings.cache_clear()

        with (
            patch("backend.src.core.redis_client.init_redis", new=AsyncMock()),
            patch("backend.src.core.redis_client.close_redis", new=AsyncMock()),
            patch("backend.src.core.database.engine") as mock_engine,
        ):
            mock_engine.dispose = AsyncMock()
            test_app = create_app()

            # Add a test route that raises NotFoundError
            from fastapi import APIRouter
            test_router = APIRouter()

            @test_router.get("/test-error")
            async def raise_error():
                raise NotFoundError("TestResource", 99)

            test_app.include_router(test_router)

            from httpx import AsyncClient, ASGITransport
            async with AsyncClient(
                transport=ASGITransport(app=test_app), base_url="http://test"
            ) as ac:
                resp = await ac.get("/test-error")
                assert resp.status_code == 404
                assert resp.json()["error"] == "NOT_FOUND"
