import pytest
from backend.src.modules.roles.application.dtos import CreateRoleDTO, PermissionDTO
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
