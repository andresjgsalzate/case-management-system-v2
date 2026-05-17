import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    JSON, Boolean, CheckConstraint, DateTime, ForeignKey, Index,
    Integer, String, Text, UniqueConstraint
)
from sqlalchemy.orm import Mapped, mapped_column

from backend.src.core.database import Base


class ForensicArtifactModel(Base):
    """Catalog of Velociraptor artifacts, synced daily."""
    __tablename__ = "forensic_artifacts"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    tenant_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=True, index=True
    )

    name: Mapped[str] = mapped_column(String(300), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    artifact_type: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    supported_os: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    parameters_schema: Mapped[list[dict] | None] = mapped_column(JSON, nullable=True)

    is_featured: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false", index=True
    )
    is_destructive: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    requires_evidence_handling: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    default_timeout_seconds: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="1800"
    )
    category: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)

    last_synced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    sync_source: Mapped[str] = mapped_column(
        String(40), nullable=False, server_default="velociraptor_api"
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true"
    )

    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="uq_forensic_artifact_tenant_name"),
        CheckConstraint(
            "artifact_type IN ('CLIENT', 'SERVER', 'NOTEBOOK', 'CLIENT_EVENT', 'SERVER_EVENT')",
            name="ck_forensic_artifact_type"
        ),
        Index("ix_forensic_artifact_featured_category", "is_featured", "category"),
    )


class ForensicHuntModel(Base):
    """A hunt launched against Velociraptor."""
    __tablename__ = "forensic_hunts"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    case_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("cases.id", ondelete="SET NULL"),
        nullable=True, index=True
    )

    artifact_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("forensic_artifacts.id"),
        nullable=False, index=True
    )
    artifact_name: Mapped[str] = mapped_column(String(300), nullable=False)
    parameters: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    target_clients: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    target_label: Mapped[str | None] = mapped_column(String(500), nullable=True)

    velo_hunt_id: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    velo_org_id: Mapped[str] = mapped_column(String(80), nullable=False)

    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="pending"
    )
    timeout_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    launched_by_user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=True
    )
    launched_by_n8n_run_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("playbook_runs.id", ondelete="SET NULL"),
        nullable=True, index=True
    )
    launched_via: Mapped[str] = mapped_column(String(20), nullable=False)

    result_summary: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    result_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    approval_request_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("approval_requests.id", ondelete="SET NULL"),
        nullable=True, index=True
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'starting', 'running', 'completed', "
            "'failed', 'timeout', 'cancelled')",
            name="ck_forensic_hunt_status"
        ),
        CheckConstraint(
            "launched_via IN ('ui_direct', 'ui_via_n8n', 'automation_n8n', 'manual_n8n')",
            name="ck_forensic_hunt_launched_via"
        ),
        CheckConstraint(
            "launched_by_user_id IS NOT NULL OR launched_by_n8n_run_id IS NOT NULL",
            name="ck_forensic_hunt_has_launcher"
        ),
        Index("ix_forensic_hunt_tenant_status_started", "tenant_id", "status", "started_at"),
        Index("ix_forensic_hunt_case_started", "case_id", "started_at"),
    )


class ForensicHuntResultModel(Base):
    """One row per host that returned results for a hunt."""
    __tablename__ = "forensic_hunt_results"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    hunt_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("forensic_hunts.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    velo_client_id: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    hostname: Mapped[str | None] = mapped_column(String(255), nullable=True)
    os: Mapped[str | None] = mapped_column(String(80), nullable=True)

    output_summary: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    output_total_rows: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )
    attachments_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )

    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="pending"
    )
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    row_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)

    collected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    velo_completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'collecting', 'completed', 'failed', 'timeout')",
            name="ck_forensic_hunt_result_status"
        ),
        UniqueConstraint("hunt_id", "velo_client_id", name="uq_hunt_client"),
        Index("ix_forensic_hunt_result_hunt_status", "hunt_id", "status"),
    )


class ForensicHuntAttachmentModel(Base):
    """Pivot linking hunts (and optionally specific result rows) to CaseAttachmentModel."""
    __tablename__ = "forensic_hunt_attachments"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    hunt_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("forensic_hunts.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    hunt_result_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("forensic_hunt_results.id", ondelete="CASCADE"),
        nullable=True, index=True
    )
    attachment_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("case_attachments.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    artifact_name: Mapped[str] = mapped_column(String(300), nullable=False)
    sha256_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    is_immutable: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint("hunt_id", "attachment_id", name="uq_hunt_attachment"),
        Index("ix_forensic_hunt_attachment_hash", "sha256_hash"),
    )
