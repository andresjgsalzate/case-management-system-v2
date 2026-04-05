import pytest
import os
import importlib
from unittest.mock import patch
from sqlalchemy.ext.asyncio import AsyncSession, AsyncEngine
from sqlalchemy.orm import DeclarativeBase


ENV = {
    "DATABASE_URL": "postgresql+asyncpg://postgres:password@localhost:5432/case_management_test",
    "REDIS_URL": "redis://localhost:6379/0",
    "SECRET_KEY": "test-secret-key-for-unit-tests-only-32ch",
}


def test_base_is_declarative():
    with patch.dict(os.environ, ENV, clear=False):
        import backend.src.core.config as config_module
        importlib.reload(config_module)
        config_module.get_settings.cache_clear()

        import backend.src.core.database as db_module
        importlib.reload(db_module)

        from backend.src.core.database import Base
        assert issubclass(Base, DeclarativeBase)


def test_engine_is_async():
    with patch.dict(os.environ, ENV, clear=False):
        import backend.src.core.config as config_module
        importlib.reload(config_module)
        config_module.get_settings.cache_clear()

        import backend.src.core.database as db_module
        importlib.reload(db_module)

        from backend.src.core.database import engine
        assert isinstance(engine, AsyncEngine)


def test_async_session_local_returns_session():
    with patch.dict(os.environ, ENV, clear=False):
        import backend.src.core.config as config_module
        importlib.reload(config_module)
        config_module.get_settings.cache_clear()

        import backend.src.core.database as db_module
        importlib.reload(db_module)

        from backend.src.core.database import AsyncSessionLocal
        session = AsyncSessionLocal()
        assert isinstance(session, AsyncSession)
        # Don't actually connect — just verify the session object type
