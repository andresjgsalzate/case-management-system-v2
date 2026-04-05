import pytest
from unittest.mock import patch
import os
import importlib


@pytest.fixture(autouse=True)
def set_env():
    env = {
        "DATABASE_URL": "postgresql+asyncpg://user:pass@localhost/db",
        "REDIS_URL": "redis://localhost:6379/0",
        "SECRET_KEY": "test-secret-key-for-unit-tests-only-32ch",
    }
    with patch.dict(os.environ, env, clear=False):
        import backend.src.core.config as config_module
        importlib.reload(config_module)
        config_module.get_settings.cache_clear()
        yield


class TestPaginationParams:
    def test_default_values(self):
        from backend.src.core.pagination import PaginationParams
        p = PaginationParams()
        assert p.page == 1
        assert p.page_size == 20
        assert p.offset == 0
        assert p.limit == 20

    def test_offset_calculation(self):
        from backend.src.core.pagination import PaginationParams
        p = PaginationParams(page=3, page_size=10)
        assert p.offset == 20
        assert p.limit == 10

    def test_page_size_max_enforced(self):
        from backend.src.core.pagination import PaginationParams
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            PaginationParams(page_size=101)


class TestRedisClient:
    def test_get_redis_raises_before_init(self):
        import backend.src.core.redis_client as redis_module
        importlib.reload(redis_module)
        with pytest.raises(RuntimeError, match="not initialized"):
            redis_module.get_redis()


class TestRequireRole:
    def test_allowed_role_returns_user_id(self):
        from backend.src.core.security import create_access_token
        from backend.src.core.dependencies import require_role
        from fastapi.security import HTTPAuthorizationCredentials

        token = create_access_token(subject=5, extra_claims={"role": "admin"})
        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

        import asyncio
        checker = require_role("admin", "manager")
        result = asyncio.run(checker(credentials=credentials))
        assert result == 5

    def test_forbidden_role_raises(self):
        from backend.src.core.security import create_access_token
        from backend.src.core.dependencies import require_role
        from backend.src.core.exceptions import ForbiddenError
        from fastapi.security import HTTPAuthorizationCredentials

        token = create_access_token(subject=5, extra_claims={"role": "viewer"})
        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

        import asyncio
        checker = require_role("admin")
        with pytest.raises(ForbiddenError):
            asyncio.run(checker(credentials=credentials))
