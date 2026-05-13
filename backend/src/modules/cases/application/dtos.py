from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class CustomFieldValueDTO(BaseModel):
    field_id: str
    value: str | None = None


class CreateCaseDTO(BaseModel):
    case_type: Literal["request", "incident", "event"] = "request"
    title: str = Field(min_length=3, max_length=500)
    description: str | None = None
    priority_id: str | None = None
    complexity: Literal["simple", "moderate", "complex"] = "simple"
    application_id: str | None = None
    origin_id: str | None = None
    service_item_id: str = Field(
        min_length=1,
        description="ID del ítem del catálogo de servicios (obligatorio)",
    )
    initial_status_slug: str | None = None
    custom_values: list[CustomFieldValueDTO] = Field(default_factory=list)


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
    case_type: Literal["request", "incident", "event"] = "request"
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
    service_item_id: str | None = None
    service_item_name: str | None = None
    service_category_id: str | None = None
    service_category_name: str | None = None
    created_by: str
    assigned_to: str | None
    assigned_user_name: str | None
    team_id: str | None
    solution_description: str | None
    is_archived: bool
    archived_at: str | None
    archived_by: str | None
    closed_at: str | None
    created_at: str
    updated_at: str

    # ─── Sub-spec 01 promotion / taxonomy fields ───
    taxonomy_id: str | None = None
    original_case_number: str | None = None
    original_case_type: Literal["request", "incident", "event"] | None = None
    promoted_at: str | None = None
    promoted_by: str | None = None
    pending_triage_until: str | None = None

    model_config = ConfigDict(from_attributes=True)
