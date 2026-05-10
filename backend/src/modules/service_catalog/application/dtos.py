from typing import Any, Literal

from pydantic import BaseModel, Field


FieldType = Literal[
    "text",
    "textarea",
    "number",
    "date",
    "datetime",
    "select",
    "radio",
    "checkbox",
    "multiselect",
    "email",
    "phone",
]


class FieldOption(BaseModel):
    value: str
    label: str


# ── Categories ────────────────────────────────────────────────────────────────


class CreateCategoryDTO(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    slug: str = Field(min_length=2, max_length=100, pattern=r"^[a-z0-9][a-z0-9\-]*$")
    description: str | None = None
    icon: str | None = None
    color: str | None = None
    sort_order: int = 0


class UpdateCategoryDTO(BaseModel):
    name: str | None = None
    description: str | None = None
    icon: str | None = None
    color: str | None = None
    is_active: bool | None = None
    sort_order: int | None = None


class CategoryResponseDTO(BaseModel):
    id: str
    name: str
    slug: str
    description: str | None
    icon: str | None
    color: str | None
    is_active: bool
    sort_order: int
    item_count: int = 0


# ── Items ─────────────────────────────────────────────────────────────────────


class CreateItemDTO(BaseModel):
    category_id: str
    name: str = Field(min_length=2, max_length=200)
    slug: str = Field(min_length=2, max_length=100, pattern=r"^[a-z0-9][a-z0-9\-]*$")
    description: str | None = None
    default_priority_id: str | None = None
    default_team_id: str | None = None
    default_level: int = Field(default=1, ge=0)
    sla_policy_id: str | None = None
    sort_order: int = 0


class UpdateItemDTO(BaseModel):
    category_id: str | None = None
    name: str | None = None
    description: str | None = None
    default_priority_id: str | None = None
    default_team_id: str | None = None
    default_level: int | None = Field(default=None, ge=0)
    sla_policy_id: str | None = None
    is_active: bool | None = None
    sort_order: int | None = None


class ItemResponseDTO(BaseModel):
    id: str
    category_id: str
    category_name: str | None = None
    name: str
    slug: str
    description: str | None
    default_priority_id: str | None
    default_team_id: str | None
    default_level: int
    sla_policy_id: str | None
    is_active: bool
    sort_order: int
    field_count: int = 0


# ── Fields ────────────────────────────────────────────────────────────────────


class CreateFieldDTO(BaseModel):
    item_id: str
    field_key: str = Field(min_length=1, max_length=80, pattern=r"^[a-z][a-z0-9_]*$")
    label: str = Field(min_length=1, max_length=200)
    field_type: FieldType
    is_required: bool = False
    placeholder: str | None = None
    help_text: str | None = None
    options: list[FieldOption] | None = None
    validation: dict[str, Any] | None = None
    sort_order: int = 0


class UpdateFieldDTO(BaseModel):
    label: str | None = None
    field_type: FieldType | None = None
    is_required: bool | None = None
    placeholder: str | None = None
    help_text: str | None = None
    options: list[FieldOption] | None = None
    validation: dict[str, Any] | None = None
    sort_order: int | None = None


class FieldResponseDTO(BaseModel):
    id: str
    item_id: str
    field_key: str
    label: str
    field_type: FieldType
    is_required: bool
    placeholder: str | None
    help_text: str | None
    options: list[FieldOption] | None
    validation: dict[str, Any] | None
    sort_order: int


class ReorderFieldsDTO(BaseModel):
    ordered_ids: list[str]


# ── Case custom values ────────────────────────────────────────────────────────


class CaseCustomValueDTO(BaseModel):
    field_id: str
    value: str | None = None


class CaseCustomValueResponseDTO(BaseModel):
    field_id: str
    field_key: str
    label: str
    field_type: FieldType
    value: str | None
    options: list[FieldOption] | None = None
