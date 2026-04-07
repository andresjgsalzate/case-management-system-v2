import pytest
from backend.src.modules.users.application.dtos import CreateUserDTO, UpdateUserDTO


def test_create_user_dto_validates_email():
    dto = CreateUserDTO(email="valid@test.com", full_name="Test User", password="pass123")
    assert dto.email == "valid@test.com"


def test_create_user_dto_invalid_email_raises():
    with pytest.raises(Exception):
        CreateUserDTO(email="not-email", full_name="Test", password="pass")


def test_create_user_dto_password_min_length():
    with pytest.raises(Exception):
        CreateUserDTO(email="a@b.com", full_name="Test", password="ab")


def test_update_user_dto_all_optional():
    dto = UpdateUserDTO()
    assert dto.full_name is None
    assert dto.role_id is None


def test_change_password_dto_min_length():
    from backend.src.modules.users.application.dtos import ChangePasswordDTO
    with pytest.raises(Exception):
        ChangePasswordDTO(current_password="old", new_password="ab")
