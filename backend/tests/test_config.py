import pytest
from unittest.mock import patch
import os
import importlib


def test_settings_loads_from_env():
    env = {
        "DATABASE_URL": "postgresql+asyncpg://user:pass@localhost/db",
        "REDIS_URL": "redis://localhost:6379/0",
        "SECRET_KEY": "test-secret-key-32-chars-minimum-x",
    }
    with patch.dict(os.environ, env, clear=False):
        import backend.src.core.config as config_module
        importlib.reload(config_module)
        config_module.get_settings.cache_clear()
        settings = config_module.get_settings()
        assert settings.DATABASE_URL == "postgresql+asyncpg://user:pass@localhost/db"
        assert settings.REDIS_URL == "redis://localhost:6379/0"
        assert settings.ACCESS_TOKEN_EXPIRE_MINUTES == 60


def test_settings_defaults():
    env = {
        "DATABASE_URL": "postgresql+asyncpg://user:pass@localhost/db",
        "REDIS_URL": "redis://localhost:6379/0",
        "SECRET_KEY": "test-secret-key-32-chars-minimum-x",
    }
    with patch.dict(os.environ, env, clear=False):
        import backend.src.core.config as config_module
        importlib.reload(config_module)
        config_module.get_settings.cache_clear()
        settings = config_module.get_settings()
        assert settings.MAX_FILE_SIZE_MB == 10
        assert settings.ALLOWED_ORIGINS == ["http://localhost:3000"]


def test_secret_key_validation_fails_for_short_key():
    env = {
        "DATABASE_URL": "postgresql+asyncpg://user:pass@localhost/db",
        "REDIS_URL": "redis://localhost:6379/0",
        "SECRET_KEY": "short",
    }
    with patch.dict(os.environ, env, clear=False):
        import backend.src.core.config as config_module
        importlib.reload(config_module)
        config_module.get_settings.cache_clear()
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            config_module.get_settings()
