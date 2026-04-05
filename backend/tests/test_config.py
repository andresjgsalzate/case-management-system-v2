import pytest
from unittest.mock import patch
import os


def test_settings_loads_from_env():
    env = {
        "DATABASE_URL": "postgresql+asyncpg://user:pass@localhost/db",
        "REDIS_URL": "redis://localhost:6379/0",
        "SECRET_KEY": "test-secret-key-32-chars-minimum-x",
    }
    with patch.dict(os.environ, env, clear=False):
        # Re-import to force reload with new env
        import importlib
        import backend.src.core.config as config_module
        importlib.reload(config_module)
        settings = config_module.get_settings()
        assert settings.DATABASE_URL == "postgresql+asyncpg://user:pass@localhost/db"
        assert settings.REDIS_URL == "redis://localhost:6379/0"
        assert settings.ACCESS_TOKEN_EXPIRE_MINUTES == 60  # default value


def test_settings_defaults():
    env = {
        "DATABASE_URL": "postgresql+asyncpg://user:pass@localhost/db",
        "REDIS_URL": "redis://localhost:6379/0",
        "SECRET_KEY": "test-secret-key-32-chars-minimum-x",
    }
    with patch.dict(os.environ, env, clear=False):
        import importlib
        import backend.src.core.config as config_module
        importlib.reload(config_module)
        settings = config_module.get_settings()
        assert settings.MAX_FILE_SIZE_MB == 10
        assert settings.ALLOWED_ORIGINS == ["http://localhost:3000"]
