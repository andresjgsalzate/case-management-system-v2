import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch
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


@pytest.fixture(scope="session", autouse=True)
def _register_all_models(set_test_env):
    # Importing main triggers the full router chain, which transitively imports
    # every SQLAlchemy model. Without this, tests that only touch a subset of
    # models (e.g. CaseModel alone) trigger configure_mappers() on a partial
    # registry and fail to resolve string-based relationships.
    import backend.src.main  # noqa: F401


def _make_mock_db():
    """Returns an async generator that yields a mock AsyncSession.

    The mock session returns None for all scalar_one_or_none() calls,
    simulating an empty database — sufficient for testing error paths
    (e.g. login with unknown user → 401) without a live DB connection.
    """
    async def _override():
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_result.scalars.return_value.all.return_value = []

        mock_session = AsyncMock()
        mock_session.execute.return_value = mock_result
        mock_session.get.return_value = None
        mock_session.commit = AsyncMock()
        mock_session.rollback = AsyncMock()
        yield mock_session

    return _override


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

        # Override the get_db dependency so no real DB connection is made
        from backend.src.core.database import get_db
        test_app.dependency_overrides[get_db] = _make_mock_db()

        async with AsyncClient(
            transport=ASGITransport(app=test_app), base_url="http://test"
        ) as ac:
            yield ac
