"""Pydantic DTOs for the integrations module (Sub-spec 04)."""
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


# ── Source CRUD ─────────────────────────────────────────────────────────


class CreateSourcePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tenant_id: str | None = None
    name: str = Field(..., min_length=1, max_length=200)
    source_type: str  # 'wazuh' | 'splunk' | ...
    auth_method: str  # 'hmac' | 'api_key' | 'bearer' | 'none'
    auth_header_name: str | None = None
    default_service_item_id: str | None = None
    default_priority_id: str | None = None
    rate_limit_per_minute: int | None = None


class UpdateSourcePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    auth_header_name: str | None = None
    default_service_item_id: str | None = None
    default_priority_id: str | None = None
    rate_limit_per_minute: int | None = None
    is_active: bool | None = None


class SourceResponse(BaseModel):
    """Read-side representation. NEVER includes the secret."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: str | None
    name: str
    source_type: str
    auth_method: str
    auth_header_name: str | None
    default_service_item_id: str | None
    default_priority_id: str | None
    is_active: bool
    rate_limit_per_minute: int | None
    last_event_received_at: datetime | None
    last_event_processed_at: datetime | None
    total_events_received: int
    total_events_failed: int
    created_at: datetime
    updated_at: datetime
    created_by: str


class CreateSourceResponse(BaseModel):
    """Response of create_source — bundles the source with its plaintext secret.
    The secret is shown to the operator ONCE and never returned again."""
    source: SourceResponse
    plaintext_secret: str
    # Suggested webhook URL the operator should configure in the upstream tool:
    webhook_url: str | None = None


class RotateSecretResponse(BaseModel):
    source_id: str
    plaintext_secret: str


# ── Inbound events (read-side) ──────────────────────────────────────────


class InboundEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    source_id: str
    tenant_id: str | None
    idempotency_key: str
    raw_payload: dict[str, Any]
    case_id: str | None
    status: str
    attempt_count: int
    max_attempts: int
    last_error: str | None
    last_attempted_at: datetime | None
    next_retry_at: datetime | None
    received_at: datetime
    processed_at: datetime | None
