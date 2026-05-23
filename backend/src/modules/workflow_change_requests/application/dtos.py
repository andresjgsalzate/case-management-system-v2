"""DTOs for the Workflow Change Request module (sub-spec 09 §3.9)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


ProposedChangeType = Literal[
    "add_step", "remove_step", "modify_step", "new_workflow",
]
StatusTransition = Literal["in_review", "approved", "rejected"]


class ProposedChange(BaseModel):
    """Structured payload describing the work the requester wants done."""

    type: ProposedChangeType
    details: str = Field(min_length=1, max_length=4000)
    # Optional attachment references — file_uploads.id strings.
    screenshots: list[str] = Field(default_factory=list)


class CreateWCRDTO(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1)
    proposed_change: ProposedChange
    workflow_id: str | None = None
    tenant_id: str | None = None


class UpdateStatusDTO(BaseModel):
    """Body of `PATCH /{id}/status` — used by the reviewer."""

    status: StatusTransition
    review_notes: str | None = None


class ImplementDTO(BaseModel):
    """Body of `POST /{id}/implement` — links the request to the realised workflow."""

    workflow_id: str = Field(min_length=1, max_length=36)
    workflow_url: str = Field(min_length=1, max_length=500)


class WCRResponseDTO(BaseModel):
    """Outbound shape — mirrors the SQLAlchemy row 1:1."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: str | None
    workflow_id: str | None
    title: str
    description: str
    proposed_change: dict
    requested_by: str
    requested_at: datetime | None
    status: str
    reviewed_by: str | None
    reviewed_at: datetime | None
    review_notes: str | None
    implemented_at: datetime | None
    implemented_in_workflow_url: str | None
