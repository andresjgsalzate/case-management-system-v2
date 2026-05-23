"""Workflow Change Request model (sub-spec 09 §3.9).

Compensating control while CMS runs on n8n Community: admins who don't
hold `n8n_editor:access` propose changes here. A reviewer (the single
admin with editor access) transitions the request through the
status machine and links it to the workflow once they implement it.

Status machine:

    pending ──► in_review ──► approved ──► implemented
                    │            │
                    └──► rejected ┘
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from backend.src.core.database import Base


VALID_STATUSES = (
    "pending",
    "in_review",
    "approved",
    "rejected",
    "implemented",
)


class WorkflowChangeRequestModel(Base):
    __tablename__ = "workflow_change_requests"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4()),
    )
    tenant_id: Mapped[str | None] = mapped_column(
        String(36), nullable=True, index=True,
    )

    # The target workflow may not exist yet — new-workflow proposals
    # arrive with workflow_id = null. ON DELETE SET NULL keeps history
    # alive when a workflow gets removed.
    workflow_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("n8n_workflows.id", ondelete="SET NULL"),
        nullable=True,
    )

    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)

    # Free-form JSON describing the proposed change:
    #   {"type": "add_step|remove_step|modify_step|new_workflow",
    #    "details": "...", "screenshots": ["uuid1", "uuid2"]}
    # Application layer doesn't enforce a schema beyond `type` being
    # one of the four values above; the UI does richer validation.
    proposed_change: Mapped[dict] = mapped_column(JSON, nullable=False)

    requested_by: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=False, index=True,
    )
    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending", server_default="pending",
    )

    reviewed_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=True,
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    review_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    implemented_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    # We snapshot the workflow URL at the moment of implementation so
    # the audit record stays meaningful even if the workflow is later
    # deleted or renamed.
    implemented_in_workflow_url: Mapped[str | None] = mapped_column(
        String(500), nullable=True,
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'in_review', 'approved', 'rejected', 'implemented')",
            name="ck_wcr_status",
        ),
        Index("ix_wcr_status_requested", "status", "requested_at"),
    )
