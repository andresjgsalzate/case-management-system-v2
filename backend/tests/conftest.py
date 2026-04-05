import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, patch
import os

from httpx import AsyncClient, ASGITransport


@pytest.fixture(scope="session", autouse=True)
def set_test_env():
    env = {
        "DATABASE_URL": "postgresql+asyncpg://user:pass@localhost/db",
        "REDIS_URL": "redis://localhost:6379/0",
        "SECRET_KEY": "test-secret-key-for-unit-tests-only-32ch",
    }
    with patch.dict(os.environ, env, clear=False):
        yield


@pytest_asyncio.fixture
async def client():
    with (
        patch("backend.src.core.redis_client.init_redis", new=AsyncMock()),
        patch("backend.src.core.redis_client.close_redis", new=AsyncMock()),
        patch("backend.src.core.database.engine") as mock_engine,
    ):
        mock_engine.dispose = AsyncMock()
        from backend.src.main import create_app
        import importlib
        import backend.src.core.config as config_module
        importlib.reload(config_module)
        config_module.get_settings.cache_clear()

        test_app = create_app()
        async with AsyncClient(
            transport=ASGITransport(app=test_app), base_url="http://test"
        ) as ac:
            yield ac
