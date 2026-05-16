"""Sub-spec 05 — n8n Bridge models.

3 tables:
- playbook_runs           — CMS-side cache of n8n workflow executions
- approval_requests       — human approval inbox for n8n Wait Node gates
- playbook_run_callbacks  — audit of every callback n8n sends

Multi-tenant: all rows have `tenant_id NOT NULL` (cases are tenant-scoped).
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from backend.src.core.database import Base


class PlaybookRunModel(Base):
    __tablename__ = "playbook_runs"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4()),
    )
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)

    case_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("cases.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )

    workflow_url: Mapped[str] = mapped_column(String(500), nullable=False)
    workflow_id: Mapped[str | None] = mapped_column(
        String(100), nullable=True, index=True,
    )

    triggered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )

    triggered_by: Mapped[str] = mapped_column(String(40), nullable=False)
    triggered_by_user: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=True,
    )

    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="triggered",
    )

    last_callback_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    callback_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0",
    )
    n8n_execution_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    trigger_payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    final_decision: Mapped[str | None] = mapped_column(String(40), nullable=True)
    final_decision_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    __table_args__ = (
        CheckConstraint(
            "status IN ('triggered', 'running', 'completed', 'failed', "
            "'timeout', 'cancelled')",
            name="ck_playbook_run_status",
        ),
        CheckConstraint(
            "triggered_by IN ('auto_triage', 'automation_rule', 'manual', "
            "'approval_resume')",
            name="ck_playbook_run_triggered_by",
        ),
        Index("ix_playbook_run_case_triggered", "case_id", "triggered_at"),
        Index("ix_playbook_run_status_triggered", "status", "triggered_at"),
    )


class ApprovalRequestModel(Base):
    __tablename__ = "approval_requests"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4()),
    )
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)

    case_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("cases.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    playbook_run_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("playbook_runs.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )

    requested_action: Mapped[str] = mapped_column(String(500), nullable=False)
    action_category: Mapped[str] = mapped_column(String(50), nullable=False)
    context_payload: Mapped[dict] = mapped_column(JSON, nullable=False)

    requested_by_workflow: Mapped[str] = mapped_column(String(200), nullable=False)
    resume_url: Mapped[str] = mapped_column(String(500), nullable=False)
    resume_hmac_secret_encrypted: Mapped[str | None] = mapped_column(
        Text, nullable=True,
    )

    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="pending",
    )
    approver_user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=True,
    )
    decided_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    decided_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    timeout_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
    )

    resume_attempted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    resume_succeeded: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false",
    )
    resume_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'approved', 'rejected', 'timeout', 'cancelled')",
            name="ck_approval_status",
        ),
        CheckConstraint(
            "(status = 'pending') OR (decided_at IS NOT NULL)",
            name="ck_approval_decided_consistency",
        ),
        Index("ix_approval_status_timeout", "status", "timeout_at"),
        Index(
            "ix_approval_tenant_status_created",
            "tenant_id", "status", "created_at",
        ),
    )


class PlaybookRunCallbackModel(Base):
    __tablename__ = "playbook_run_callbacks"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4()),
    )
    playbook_run_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("playbook_runs.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )

    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False, index=True,
    )

    action: Mapped[str] = mapped_column(String(50), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)

    success: Mapped[bool] = mapped_column(Boolean, nullable=False)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    response_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    __table_args__ = (
        Index("ix_callback_run_received", "playbook_run_id", "received_at"),
    )
