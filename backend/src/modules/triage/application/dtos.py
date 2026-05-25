"""Pydantic DTOs for the SOC triage module.

Literal enums mirror the CHECK constraints declared in the migration
(`e2a7c3f9b1d4_triage_module.py`). Slug values are ASCII (no accents)
so they're URL-safe, queryable, and stable across language imports.
"""
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


# ─── Enums shared by request + response ─────────────────────────────


# Severity = the analyst's read of the alert. "falso_positivo" short-circuits
# the prioritization matrix in the use case.
AlertSeverity = Literal["critico", "alto", "medio", "bajo", "falso_positivo"]

# Origin: drives which side of the sub-taxonomy's impact (internal_impact_context
# vs external_impact_context) is read for the "Impacto potencial" auto-fill.
ContextOriginType = Literal["origen_interno", "origen_externo"]

# Asset criticality: 4-level scale (no falso_positivo here -- doesn't make
# sense for an asset). Aliasable with TLP per spec section 2.2.b.
AssetCriticality = Literal["critico", "alto", "medio", "bajo"]


# ─── Catalog DTOs ───────────────────────────────────────────────────


class TriageToolTypeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    description: str | None
    is_active: bool


class TriageToolActionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    is_active: bool


class TriageSlaPolicyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    priority_id: str
    sla_minutes: int | None  # NULL = N/A (Falso Positivo)
    is_active: bool


# ─── Catalog admin payloads (Phase 5 CRUD) ──────────────────────────


class CreateToolTypePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=2000)


class UpdateToolTypePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=2000)
    is_active: bool | None = None


class CreateToolActionPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=50)


class UpdateToolActionPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str | None = Field(default=None, min_length=1, max_length=50)
    is_active: bool | None = None


class CreateSlaPolicyPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    priority_id: str
    # NULL = N/A (e.g. Falso Positivo). >=0 otherwise.
    sla_minutes: int | None = Field(default=None, ge=0)


class UpdateSlaPolicyPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sla_minutes: int | None = Field(default=None, ge=0)
    is_active: bool | None = None


# ─── Main: case_triage request + response ───────────────────────────


class CreateTriagePayload(BaseModel):
    """Body for POST /cases/{id}/triage. Creates a new triage revision."""
    model_config = ConfigDict(extra="forbid")

    # Required: classification + the 3 inputs of the priority matrix.
    sub_taxonomy_id: str
    alert_severity: AlertSeverity
    context_origin_type: ContextOriginType
    asset_criticality: AssetCriticality

    # Optional catalog references
    tool_type_id: str | None = None
    tool_action_id: str | None = None

    # Optional free-form fields
    context_origin_detail: str | None = Field(default=None, max_length=500)
    related_asset: str | None = Field(default=None, max_length=500)
    alert_duration_seconds: int | None = Field(default=None, ge=0)
    alert_repetitions: int = Field(default=1, ge=1)

    # Optional narratives
    analysis_narrative: str | None = None
    behavior_narrative: str | None = None
    recommendations: str | None = None

    # Optional attachment references (must be existing case_attachments
    # belonging to the same case -- validated server-side).
    evidence_attachment_id: str | None = None
    behavior_attachment_id: str | None = None


class CaseTriageResponse(BaseModel):
    """Single triage revision projection."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    case_id: str
    version: int
    triaged_by_user_id: str
    triaged_at: datetime

    case_title_snapshot: str
    case_tenant_name_snapshot: str | None

    sub_taxonomy_id: str
    alert_severity: str
    context_origin_type: str
    asset_criticality: str

    tool_type_id: str | None
    tool_action_id: str | None

    context_origin_detail: str | None
    related_asset: str | None
    alert_duration_seconds: int | None
    alert_repetitions: int

    analysis_narrative: str | None
    behavior_narrative: str | None
    recommendations: str | None

    evidence_attachment_id: str | None
    behavior_attachment_id: str | None

    calculated_priority_id: str | None
    calculated_score: Decimal | None
    calculated_sla_minutes: int | None

    created_at: datetime


class TriageWithContext(BaseModel):
    """Response shape for the "current triage" endpoint: includes the
    auto-derived fields (parent taxonomy info, impact resolution, etc.)
    so the UI doesn't have to re-query the taxonomy.
    """
    triage: CaseTriageResponse

    # Auto-derived
    parent_taxonomy_id: str | None
    parent_taxonomy_name: str | None
    sub_taxonomy_name: str
    # Lookup result from sub_taxonomy + context_origin_type
    impacto_potencial: str | None
