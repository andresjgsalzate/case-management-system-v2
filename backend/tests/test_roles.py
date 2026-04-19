import pytest
from backend.src.modules.roles.application.dtos import CreateRoleDTO, PermissionDTO, UpdateRoleDTO
from backend.src.modules.roles.domain.entities import Role, Permission


def test_role_entity_creation():
    role = Role(id="r1", tenant_id=None, name="Agent", description="Standard agent")
    assert role.name == "Agent"


def test_permission_scope_valid():
    perm = Permission(role_id="r1", module="cases", action="read", scope="team")
    assert perm.scope == "team"


def test_permission_invalid_scope_raises():
    with pytest.raises(ValueError):
        Permission(role_id="r1", module="cases", action="read", scope="invalid")


def test_create_role_dto_validation():
    dto = CreateRoleDTO(name="Manager", description="Team manager")
    assert dto.name == "Manager"
    assert dto.permissions == []


def test_create_role_dto_with_permissions():
    dto = CreateRoleDTO(
        name="Agent",
        permissions=[PermissionDTO(module="cases", action="read", scope="team")]
    )
    assert len(dto.permissions) == 1
    assert dto.permissions[0].scope == "team"


def test_permission_dto_default_scope():
    perm = PermissionDTO(module="users", action="read")
    assert perm.scope == "own"


def test_create_role_dto_defaults_level_to_1():
    dto = CreateRoleDTO(name="Agent")
    assert dto.level == 1


def test_create_role_dto_accepts_custom_level():
    dto = CreateRoleDTO(name="N2 Agent", level=2)
    assert dto.level == 2


def test_create_role_dto_rejects_negative_level():
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        CreateRoleDTO(name="Bad", level=-1)


def test_update_role_dto_has_optional_level():
    assert UpdateRoleDTO().level is None
    dto = UpdateRoleDTO(level=3)
    assert dto.level == 3


def test_role_response_dto_carries_level():
    from backend.src.modules.roles.application.dtos import RoleResponseDTO
    r = RoleResponseDTO(
        id="r1", name="Agent", description=None,
        created_at="2026-04-18T00:00:00Z", permissions=[], level=2,
    )
    assert r.level == 2
