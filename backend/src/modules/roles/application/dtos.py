from pydantic import BaseModel, Field
from typing import Literal


class PermissionDTO(BaseModel):
    module: str
    action: str
    scope: Literal["own", "team", "all"] = "own"


class CreateRoleDTO(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    description: str | None = None
    permissions: list[PermissionDTO] = []


class UpdateRoleDTO(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=100)
    description: str | None = None


class RoleResponseDTO(BaseModel):
    id: str
    name: str
    description: str | None
    created_at: str
    permissions: list[PermissionDTO] = []

    model_config = {"from_attributes": True}
