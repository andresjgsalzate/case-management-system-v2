from typing import Literal
from pydantic import BaseModel, Field


class CreateCaseDTO(BaseModel):
    title: str = Field(min_length=3, max_length=500)
    description: str | None = None
    priority_id: str
    complexity: Literal["simple", "moderate", "complex"] = "simple"
    application_id: str | None = None
    origin_id: str | None = None


class UpdateCaseDTO(BaseModel):
    title: str | None = Field(default=None, min_length=3, max_length=500)
    description: str | None = None
    complexity: Literal["simple", "moderate", "complex"] | None = None
    application_id: str | None = None
    origin_id: str | None = None


class TransitionCaseDTO(BaseModel):
    target_status_id: str
    solution_description: str | None = None


class AssignCaseDTO(BaseModel):
    assigned_to: str | None = None  # user_id, None = desasignar
    team_id: str | None = None


class CaseResponseDTO(BaseModel):
    id: str
    case_number: str
    title: str
    description: str | None
    status_id: str
    status_name: str
    status_slug: str
    status_color: str
    priority_id: str
    priority_name: str
    priority_color: str
    complexity: str
    application_id: str | None
    application_name: str | None
    origin_id: str | None
    origin_name: str | None
    created_by: str
    assigned_to: str | None
    team_id: str | None
    solution_description: str | None
    is_archived: bool
    closed_at: str | None
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True
