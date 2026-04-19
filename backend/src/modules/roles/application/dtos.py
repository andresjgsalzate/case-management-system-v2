from pydantic import BaseModel, Field
from typing import Literal


class PermissionDTO(BaseModel):
    module: str
    action: str
    scope: Literal["own", "team", "all"] = "own"


class CreateRoleDTO(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    description: str | None = None
    level: int = Field(default=1, ge=0)
    permissions: list[PermissionDTO] = []


class UpdateRoleDTO(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=100)
    description: str | None = None
    level: int | None = Field(default=None, ge=0)


class RoleResponseDTO(BaseModel):
    id: str
    name: str
    description: str | None
    created_at: str
    level: int = 1
    permissions: list[PermissionDTO] = []

    model_config = {"from_attributes": True}
