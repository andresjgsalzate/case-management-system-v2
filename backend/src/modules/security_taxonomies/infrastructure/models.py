"""Sub-spec 02 — Security Taxonomies models.

4 tables:
- security_taxonomies         — main hierarchical taxonomy with TUIC code, governance, triage mode
- security_taxonomies_audit_log — field-level diff history
- taxonomy_notifications       — N:M with teams (notify_phase, notify_channel)
- taxonomy_catalog_mappings    — N:M with service_catalog_items (is_default per taxonomy)

Multi-tenant: tenant_id NULL = global; non-NULL = tenant-specific override (full copy via fork).

Note: prioritization_formula_id is declared as plain String(36) here.
The ForeignKey to prioritization_formulas.id is added by Sub-spec 03 migration
once that table exists.
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
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from backend.src.core.database import Base


class SecurityTaxonomyModel(Base):
    __tablename__ = "security_taxonomies"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    tenant_id: Mapped[str | None] = mapped_column(
        String(36), nullable=True, index=True
    )

    tuic_code: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    parent_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("security_taxonomies.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    attack_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    attack_subtype: Mapped[str | None] = mapped_column(String(100), nullable=True)
    internal_impact_context: Mapped[str | None] = mapped_column(Text, nullable=True)
    external_impact_context: Mapped[str | None] = mapped_column(Text, nullable=True)

    managed_by_team_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("teams.id", ondelete="SET NULL"),
        nullable=True,
    )

    default_case_type: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="event"
    )
    requires_ticket: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    triage_mode: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="auto"
    )
    delegated_workflow_id: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )
    triage_timeout_seconds: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="300"
    )

    tlp_default: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="amber"
    )

    # FK wired by Sub-spec 03 Task 2 (prioritization_formulas table now exists).
    prioritization_formula_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("prioritization_formulas.id", ondelete="SET NULL"),
        nullable=True,
    )

    mitre_techniques: Mapped[list] = mapped_column(
        JSON, nullable=False, server_default=text("'[]'::json")
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true"
    )

    forked_from_global_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("security_taxonomies.id", ondelete="SET NULL"),
        nullable=True,
    )
    forked_from_global_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    created_by: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=False
    )
    updated_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=True
    )

    __table_args__ = (
        UniqueConstraint("tenant_id", "tuic_code", name="uq_taxonomy_tenant_tuic"),
        CheckConstraint(
            "default_case_type IN ('event', 'incident')",
            name="ck_taxonomy_default_case_type",
        ),
        CheckConstraint(
            "triage_mode IN ('auto', 'delegate_to_n8n')",
            name="ck_taxonomy_triage_mode",
        ),
        CheckConstraint(
            "tlp_default IN ('white', 'green', 'amber', 'red')",
            name="ck_taxonomy_tlp",
        ),
        CheckConstraint(
            "(triage_mode = 'auto') OR "
            "(triage_mode = 'delegate_to_n8n' AND delegated_workflow_id IS NOT NULL)",
            name="ck_taxonomy_delegate_requires_workflow",
        ),
        CheckConstraint(
            "(forked_from_global_id IS NULL AND forked_from_global_at IS NULL) OR "
            "(forked_from_global_id IS NOT NULL AND forked_from_global_at IS NOT NULL)",
            name="ck_taxonomy_fork_consistency",
        ),
        CheckConstraint(
            "(forked_from_global_id IS NULL) OR (tenant_id IS NOT NULL)",
            name="ck_taxonomy_fork_requires_tenant",
        ),
        Index("ix_taxonomy_tenant_active", "tenant_id", "is_active"),
        Index("ix_taxonomy_parent", "parent_id"),
    )


class SecurityTaxonomyAuditLogModel(Base):
    __tablename__ = "security_taxonomies_audit_log"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    taxonomy_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("security_taxonomies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    changed_by: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=False
    )
    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )

    change_type: Mapped[str] = mapped_column(String(30), nullable=False)
    field_changes: Mapped[dict] = mapped_column(
        JSON, nullable=False, server_default=text("'{}'::json")
    )
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index(
            "ix_taxonomy_audit_taxonomy_changed_at",
            "taxonomy_id",
            "changed_at",
        ),
        CheckConstraint(
            "change_type IN ('created', 'updated', 'soft_deleted', "
            "'activated', 'forked', 'refreshed_from_global')",
            name="ck_taxonomy_audit_change_type",
        ),
    )


class TaxonomyNotificationModel(Base):
    __tablename__ = "taxonomy_notifications"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    taxonomy_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("security_taxonomies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    team_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("teams.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    notify_phase: Mapped[str] = mapped_column(String(40), nullable=False)
    notify_channel: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="email"
    )
    escalation_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "taxonomy_id",
            "team_id",
            "notify_phase",
            name="uq_taxonomy_notif_tax_team_phase",
        ),
        CheckConstraint(
            "notify_phase IN ('triage', 'created', 'critical_priority', "
            "'sla_breach', 'resolved', 'promoted')",
            name="ck_taxonomy_notif_phase",
        ),
        CheckConstraint(
            "notify_channel IN ('email', 'chat', 'sms', 'all')",
            name="ck_taxonomy_notif_channel",
        ),
    )


class TaxonomyCatalogMappingModel(Base):
    __tablename__ = "taxonomy_catalog_mappings"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    taxonomy_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("security_taxonomies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    service_catalog_item_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("service_catalog_items.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    is_default: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    priority_order: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )

    __table_args__ = (
        UniqueConstraint(
            "taxonomy_id",
            "service_catalog_item_id",
            name="uq_taxonomy_catalog_map",
        ),
        Index(
            "ux_taxonomy_default",
            "taxonomy_id",
            unique=True,
            postgresql_where=text("is_default = true"),
        ),
    )
