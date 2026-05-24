"""SOC Triage models (Phase 2 of docs/specs/triage.md).

4 tables:

  - TriageToolTypeModel    — catalog: FW Externo, EDR, ... (xlsx Herramientas)
  - TriageToolActionModel  — catalog: Monitoreo, Bloqueo, ...
  - TriageSlaPolicyModel   — per-priority SLA in minutes (NULL = N/A, e.g. FP)
  - CaseTriageModel        — main: one row per triage *revision* of a case

Multi-tenant: catalog tables use the tenant_id NULL = global pattern.
CaseTriageModel inherits tenant scoping from its parent case via FK.

Calculation results (priority + score + sla minutes) are denormalised on the
triage row so list / report queries don't have to hit prioritization_*.
The truth of *how* they were calculated lives in case_priority_calculations
(written by the prioritization engine when the triage triggers a recalc).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from backend.src.core.database import Base


# ─── Catalog tables ─────────────────────────────────────────────────


class TriageToolTypeModel(Base):
    """Source-of-event tools (xlsx `Herramientas`)."""
    __tablename__ = "triage_tool_types"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4()),
    )
    tenant_id: Mapped[str | None] = mapped_column(
        String(36), nullable=True, index=True,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc), nullable=False,
    )

    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="uq_tool_type_tenant_name"),
    )


class TriageToolActionModel(Base):
    """Action applied on the tool. xlsx calls this "Acción aplicada"
    (Monitoreo / Bloqueo / ...). Renamed from the original spec name
    `triage_tool_modes` to match client nomenclature.
    """
    __tablename__ = "triage_tool_actions"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4()),
    )
    tenant_id: Mapped[str | None] = mapped_column(
        String(36), nullable=True, index=True,
    )
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc), nullable=False,
    )

    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="uq_tool_action_tenant_name"),
    )


class TriageSlaPolicyModel(Base):
    """SLA in minutes per priority level (xlsx `Priorización!R16-R22`).
    `sla_minutes` NULL means N/A — used for Falso Positivo where there
    is no notification deadline.
    """
    __tablename__ = "triage_sla_policies"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4()),
    )
    tenant_id: Mapped[str | None] = mapped_column(
        String(36), nullable=True, index=True,
    )
    priority_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("case_priorities.id", ondelete="CASCADE"),
        nullable=False,
    )
    sla_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc), nullable=False,
    )

    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "priority_id", name="uq_sla_policy_tenant_priority"
        ),
    )


# ─── Main: case_triages ─────────────────────────────────────────────


class CaseTriageModel(Base):
    """One row per triage *revision* of a case. The current triage is
    the row with the highest `version` for the case (ORDER BY version DESC).
    """
    __tablename__ = "case_triages"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4()),
    )
    case_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("cases.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    triaged_by_user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=False,
    )
    triaged_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc), nullable=False,
    )

    # Snapshot at triage time (avoids drift if case is later edited).
    case_title_snapshot: Mapped[str] = mapped_column(String(500), nullable=False)
    case_tenant_name_snapshot: Mapped[str | None] = mapped_column(
        String(200), nullable=True,
    )

    # Classification (sub_taxonomy is the leaf; parent inferred from it)
    sub_taxonomy_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("security_taxonomies.id"),
        nullable=False,
    )

    # Fixed enums (CHECK constraints in migration mirror these).
    alert_severity: Mapped[str] = mapped_column(String(20), nullable=False)
    context_origin_type: Mapped[str] = mapped_column(String(20), nullable=False)
    asset_criticality: Mapped[str] = mapped_column(String(20), nullable=False)

    # Catalog FKs
    tool_type_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("triage_tool_types.id"),
        nullable=True,
    )
    tool_action_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("triage_tool_actions.id"),
        nullable=True,
    )

    # Free-form fields
    context_origin_detail: Mapped[str | None] = mapped_column(String(500), nullable=True)
    related_asset: Mapped[str | None] = mapped_column(String(500), nullable=True)
    alert_duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    alert_repetitions: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="1",
    )

    # Narratives
    analysis_narrative: Mapped[str | None] = mapped_column(Text, nullable=True)
    behavior_narrative: Mapped[str | None] = mapped_column(Text, nullable=True)
    recommendations: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Semantic attachments (existing case_attachments rows)
    evidence_attachment_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("case_attachments.id", ondelete="SET NULL"),
        nullable=True,
    )
    behavior_attachment_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("case_attachments.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Calculation result (denormalised)
    calculated_priority_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("case_priorities.id"), nullable=True,
    )
    calculated_score: Mapped[Decimal | None] = mapped_column(
        Numeric(precision=4, scale=2), nullable=True,
    )
    calculated_sla_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc), nullable=False,
    )

    __table_args__ = (
        UniqueConstraint("case_id", "version", name="uq_triage_case_version"),
        CheckConstraint(
            "alert_severity IN ('critico', 'alto', 'medio', 'bajo', 'falso_positivo')",
            name="ck_triage_alert_severity",
        ),
        CheckConstraint(
            "context_origin_type IN ('origen_interno', 'origen_externo')",
            name="ck_triage_context_origin_type",
        ),
        CheckConstraint(
            "asset_criticality IN ('critico', 'alto', 'medio', 'bajo')",
            name="ck_triage_asset_criticality",
        ),
    )
