"""Sub-spec 08 — Alert Report Generator data models.

Three tables:

- ``alert_report_templates`` — mutable head row per template. Holds the
  pointer to the current immutable version (``current_version_id``).
- ``alert_report_template_versions`` — immutable snapshots. Editing a
  template creates a new row; old reports remain regenerable.
- ``case_generated_reports`` — one row per PDF generation. Carries the
  ``data_snapshot`` + ``pdf_sha256`` that constitute the chain-of-custody
  record. The PDF itself lives in ``case_attachments`` (linked by
  ``attachment_id`` with ``ondelete=RESTRICT`` to block deletion while a
  report references the blob).
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    JSON, Boolean, CheckConstraint, DateTime, ForeignKey, Index,
    Integer, String, Text, UniqueConstraint, text,
)
from sqlalchemy.orm import Mapped, mapped_column

from backend.src.core.database import Base


class AlertReportTemplateModel(Base):
    """Mutable head row pointing at the current immutable template version."""
    __tablename__ = "alert_report_templates"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    tenant_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=True, index=True,
    )

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    code: Mapped[str] = mapped_column(String(80), nullable=False)

    # Circular FK — ``use_alter=True`` defers the constraint creation so
    # the table can be created without the versions table existing yet.
    current_version_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey(
            "alert_report_template_versions.id",
            use_alter=True,
            name="fk_alert_report_template_current_version",
        ),
        nullable=True,
    )
    current_version_number: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )

    is_default: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true"
    )

    created_by_user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "code",
            name="uq_alert_report_template_tenant_code",
        ),
        Index(
            "ux_alert_report_template_default_per_tenant",
            "tenant_id",
            unique=True,
            postgresql_where=text("is_default IS TRUE AND is_active IS TRUE"),
        ),
    )


class AlertReportTemplateVersionModel(Base):
    """Immutable snapshot of a template at a point in time."""
    __tablename__ = "alert_report_template_versions"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    template_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("alert_report_templates.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )

    version: Mapped[int] = mapped_column(Integer, nullable=False)

    name_snapshot: Mapped[str] = mapped_column(String(200), nullable=False)
    header_config: Mapped[dict] = mapped_column(JSON, nullable=False)
    footer_config: Mapped[dict] = mapped_column(JSON, nullable=False)
    blocks: Mapped[list[dict]] = mapped_column(JSON, nullable=False)
    css_overrides: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_by_user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    change_summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "template_id", "version", name="uq_template_version",
        ),
        Index(
            "ix_template_version_template_created",
            "template_id", "created_at",
        ),
    )


class CaseGeneratedReportModel(Base):
    """Immutable record of a single PDF generation."""
    __tablename__ = "case_generated_reports"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    case_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("cases.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )

    template_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("alert_report_templates.id"),
        nullable=False,
    )
    template_version_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("alert_report_template_versions.id"),
        nullable=False,
    )
    template_version_number: Mapped[int] = mapped_column(
        Integer, nullable=False
    )

    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    generated_by_user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=True
    )
    generated_by_n8n_run_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("playbook_runs.id", ondelete="SET NULL"),
        nullable=True,
    )
    generated_via: Mapped[str] = mapped_column(String(20), nullable=False)

    attachment_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("case_attachments.id", ondelete="RESTRICT"),
        nullable=False,
    )
    pdf_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    pdf_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)

    data_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False)
    generation_context: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    __table_args__ = (
        CheckConstraint(
            "generated_via IN ('manual_ui', 'n8n_api')",
            name="ck_generated_report_via",
        ),
        CheckConstraint(
            "generated_by_user_id IS NOT NULL OR "
            "generated_by_n8n_run_id IS NOT NULL",
            name="ck_generated_report_has_actor",
        ),
        Index(
            "ix_generated_report_case_generated",
            "case_id", "generated_at",
        ),
        Index(
            "ix_generated_report_tenant_generated",
            "tenant_id", "generated_at",
        ),
    )
