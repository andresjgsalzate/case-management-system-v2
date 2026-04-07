import pytest
from backend.src.modules.auth.application.dtos import LoginDTO, TokenResponseDTO


def test_login_dto_validates_email():
    dto = LoginDTO(email="test@test.com", password="secret")
    assert dto.email == "test@test.com"


def test_login_dto_invalid_email_raises():
    with pytest.raises(Exception):
        LoginDTO(email="not-an-email", password="secret")


def test_token_response_dto_default_type():
    dto = TokenResponseDTO(
        access_token="abc",
        refresh_token="xyz",
        user={"id": "1", "email": "a@b.com"}
    )
    assert dto.token_type == "bearer"


def test_hash_refresh_token_deterministic():
    from backend.src.modules.auth.application.use_cases import _hash_refresh_token
    token = "my-refresh-token"
    assert _hash_refresh_token(token) == _hash_refresh_token(token)
    assert len(_hash_refresh_token(token)) == 64  # SHA-256 hex = 64 chars


@pytest.mark.asyncio
async def test_login_wrong_credentials_raises_unauthorized(client):
    response = await client.post("/api/v1/auth/login", json={
        "email": "noexiste@test.com",
        "password": "wrong"
    })
    assert response.status_code == 401
