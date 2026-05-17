"""Pydantic DTOs for the forensic module."""
from datetime import datetime

from pydantic import BaseModel, Field


class ClientSummary(BaseModel):
    """Velociraptor client (host) summary returned to the UI."""
    client_id: str
    hostname: str | None = None
    os: str | None = None
    last_seen_at: datetime | None = None


class LaunchHuntDTO(BaseModel):
    """Input from the UI or n8n bridge when starting a hunt."""
    artifact_id: str
    parameters: dict = Field(default_factory=dict)
    target_clients: list[str]
    timeout_seconds: int | None = None
    case_id: str | None = None
    approval_request_id: str | None = None


class HuntSummary(BaseModel):
    """Compact projection of a hunt for list views and SSE updates."""
    id: str
    case_id: str | None
    artifact_name: str
    target_label: str | None
    status: str
    started_at: datetime
    completed_at: datetime | None
    launched_via: str
    result_hash: str | None
