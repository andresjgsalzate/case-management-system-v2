"""Pydantic DTOs for the prioritization router."""
from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class CriterionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: str | None
    code: str
    name: str
    description: str | None
    data_source: str
    source_field_key: str | None
    missing_data_strategy: str
    default_value: int | None
    is_active: bool
    sort_order: int


class ScaleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    criterion_id: str
    label: str
    numeric_value: int
    color: str | None
    sort_order: int


class FormulaResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: str | None
    logical_key: str
    version: int
    name: str
    description: str | None
    is_active: bool
    effective_from: datetime
    effective_to: datetime | None
    superseded_by_id: str | None
    created_at: datetime
    created_by: str


class FormulaCriterionWeight(BaseModel):
    """Inline DTO for create_formula payload entries."""
    model_config = ConfigDict(extra="forbid")

    code: str
    weight: Decimal = Field(..., gt=0, le=1)


class FormulaThresholdEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    min_value: Decimal
    max_value: Decimal
    priority_name: str  # case_priorities.name (Baja/Media/Alta/Critica)


class CreateFormulaVersionPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tenant_id: str | None = None
    logical_key: str
    base_version_id: str | None = None
    name: str
    description: str | None = None
    criteria_weights: list[FormulaCriterionWeight]
    thresholds: list[FormulaThresholdEntry]


class CalculationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    case_id: str
    formula_id: str
    formula_version: int
    inputs: dict[str, Any]
    weighted_sum: Decimal
    resulting_priority_id: str
    calculated_at: datetime
    triggered_by: str
    triggered_by_user: str | None
