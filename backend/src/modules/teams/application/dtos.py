from pydantic import BaseModel, Field
from typing import Literal


class CreateTeamDTO(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    description: str | None = None


class UpdateTeamDTO(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=200)
    description: str | None = None


class AddMemberDTO(BaseModel):
    user_id: str
    team_role: Literal["manager", "lead", "member"] = "member"


class TeamMemberResponseDTO(BaseModel):
    user_id: str
    full_name: str | None
    email: str | None
    team_role: str
    joined_at: str


class TeamResponseDTO(BaseModel):
    id: str
    name: str
    description: str | None
    created_at: str
    members: list[TeamMemberResponseDTO] = []

    model_config = {"from_attributes": True}
