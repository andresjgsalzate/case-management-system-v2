"""Pydantic DTOs for the security_taxonomies module."""
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class TaxonomyCreatePayload(BaseModel):
    """Payload for creating a new taxonomy.

    tenant_id is optional: NULL means create as global (requires manage_global perm).
    """
    model_config = ConfigDict(extra="forbid")

    tenant_id: str | None = None
    tuic_code: str = Field(..., min_length=1, max_length=50)
    name: str = Field(..., min_length=1, max_length=300)
    description: str | None = None
    parent_id: str | None = None

    attack_type: str | None = None
    attack_subtype: str | None = None
    internal_impact_context: str | None = None
    external_impact_context: str | None = None

    managed_by_team_id: str | None = None
    default_case_type: str = "event"  # 'event' | 'incident'
    requires_ticket: bool = False
    triage_mode: str = "auto"  # 'auto' | 'delegate_to_n8n'
    delegated_workflow_id: str | None = None
    triage_timeout_seconds: int = 300
    tlp_default: str = "amber"  # 'white' | 'green' | 'amber' | 'red'
    prioritization_formula_id: str | None = None
    mitre_techniques: list[str] = Field(default_factory=list)


class TaxonomyUpdatePayload(BaseModel):
    """Partial update — all fields optional."""
    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    description: str | None = None
    parent_id: str | None = None
    attack_type: str | None = None
    attack_subtype: str | None = None
    internal_impact_context: str | None = None
    external_impact_context: str | None = None
    managed_by_team_id: str | None = None
    default_case_type: str | None = None
    requires_ticket: bool | None = None
    triage_mode: str | None = None
    delegated_workflow_id: str | None = None
    triage_timeout_seconds: int | None = None
    tlp_default: str | None = None
    prioritization_formula_id: str | None = None
    mitre_techniques: list[str] | None = None
    is_active: bool | None = None


class NotificationCreatePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    team_id: str
    notify_phase: str
    notify_channel: str = "email"
    escalation_minutes: int | None = None


class CatalogMappingCreatePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    service_catalog_item_id: str
    is_default: bool = False
    priority_order: int = 0


class TaxonomyResponse(BaseModel):
    """Serialization output."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: str | None
    tuic_code: str
    name: str
    description: str | None
    parent_id: str | None
    attack_type: str | None
    attack_subtype: str | None
    internal_impact_context: str | None
    external_impact_context: str | None
    managed_by_team_id: str | None
    default_case_type: str
    requires_ticket: bool
    triage_mode: str
    delegated_workflow_id: str | None
    triage_timeout_seconds: int
    tlp_default: str
    prioritization_formula_id: str | None
    mitre_techniques: list[Any]
    is_active: bool
    forked_from_global_id: str | None
    forked_from_global_at: datetime | None
    created_at: datetime
    updated_at: datetime
    created_by: str
    updated_by: str | None
