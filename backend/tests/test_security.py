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


class TestPasswordHashing:
    def test_hash_is_not_plain_text(self):
        from backend.src.core.security import hash_password
        hashed = hash_password("mysecretpassword")
        assert hashed != "mysecretpassword"
        assert hashed.startswith("$2b$")

    def test_verify_correct_password(self):
        from backend.src.core.security import hash_password, verify_password
        hashed = hash_password("mysecretpassword")
        assert verify_password("mysecretpassword", hashed) is True

    def test_verify_wrong_password(self):
        from backend.src.core.security import hash_password, verify_password
        hashed = hash_password("mysecretpassword")
        assert verify_password("wrongpassword", hashed) is False


class TestJWT:
    def test_create_and_decode_token(self):
        from backend.src.core.security import create_access_token, decode_access_token
        token = create_access_token(subject=123)
        payload = decode_access_token(token)
        assert payload["sub"] == "123"

    def test_extra_claims_in_token(self):
        from backend.src.core.security import create_access_token, decode_access_token
        token = create_access_token(subject=1, extra_claims={"role": "admin"})
        payload = decode_access_token(token)
        assert payload["role"] == "admin"

    def test_invalid_token_raises_unauthorized(self):
        from backend.src.core.security import decode_access_token
        from backend.src.core.exceptions import UnauthorizedError
        with pytest.raises(UnauthorizedError):
            decode_access_token("invalid.token.here")

    def test_expired_token_raises_unauthorized(self):
        from datetime import timedelta
        from backend.src.core.security import create_access_token, decode_access_token
        from backend.src.core.exceptions import UnauthorizedError
        token = create_access_token(subject=1, expires_delta=timedelta(seconds=-1))
        with pytest.raises(UnauthorizedError):
            decode_access_token(token)
