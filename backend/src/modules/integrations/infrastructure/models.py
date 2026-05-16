"""Sub-spec 04 — Inbound Integrations & Wazuh Adapter models.

4 tables:
- integration_sources           — configured webhook origins (Wazuh, Splunk, …)
- integration_mappings          — generic JSONPath-driven field extraction (non-Wazuh)
- inbound_events                — raw payload audit + retry queue
- wazuh_rule_to_taxonomy_map    — Wazuh-specific rule.id/groups → taxonomy

Multi-tenant: sources usually tenant-specific (NULL only for shared origins).
Wazuh taxonomy map supports global (NULL tenant_id) + per-source overrides.
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
)
from sqlalchemy.orm import Mapped, mapped_column

from backend.src.core.database import Base


class IntegrationSourceModel(Base):
    __tablename__ = "integration_sources"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4()),
    )
    tenant_id: Mapped[str | None] = mapped_column(
        String(36), nullable=True, index=True,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    source_type: Mapped[str] = mapped_column(String(40), nullable=False)
    auth_method: Mapped[str] = mapped_column(String(20), nullable=False)
    auth_secret_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    auth_header_name: Mapped[str | None] = mapped_column(String(50), nullable=True)

    default_service_item_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("service_catalog_items.id", ondelete="SET NULL"),
        nullable=True,
    )
    default_priority_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("case_priorities.id", ondelete="SET NULL"),
        nullable=True,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true",
    )
    rate_limit_per_minute: Mapped[int | None] = mapped_column(Integer, nullable=True)

    last_event_received_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    last_event_processed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    total_events_received: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0",
    )
    total_events_failed: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    created_by: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=False,
    )

    __table_args__ = (
        CheckConstraint(
            "source_type IN ('wazuh', 'splunk', 'sentinel', 'crowdstrike', "
            "'qradar', 'wazuh_velociraptor', 'custom')",
            name="ck_source_type",
        ),
        CheckConstraint(
            "auth_method IN ('hmac', 'api_key', 'bearer', 'none')",
            name="ck_source_auth_method",
        ),
        Index("ix_source_tenant_active", "tenant_id", "is_active"),
    )


class IntegrationMappingModel(Base):
    __tablename__ = "integration_mappings"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4()),
    )
    source_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("integration_sources.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    target_field: Mapped[str] = mapped_column(String(100), nullable=False)
    json_path: Mapped[str] = mapped_column(String(300), nullable=False)
    transform: Mapped[str | None] = mapped_column(String(50), nullable=True)
    default_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_required: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false",
    )
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")

    __table_args__ = (
        UniqueConstraint(
            "source_id", "target_field", name="uq_mapping_source_field",
        ),
    )


class InboundEventModel(Base):
    __tablename__ = "inbound_events"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4()),
    )
    source_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("integration_sources.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )
    tenant_id: Mapped[str | None] = mapped_column(
        String(36), nullable=True, index=True,
    )
    idempotency_key: Mapped[str] = mapped_column(
        String(128), nullable=False, unique=True, index=True,
    )
    raw_payload: Mapped[dict] = mapped_column(JSON, nullable=False)

    case_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("cases.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )

    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="pending",
    )
    attempt_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0",
    )
    max_attempts: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="3",
    )
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_attempted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    next_retry_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True,
    )

    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False, index=True,
    )
    processed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'processing', 'processed', 'failed', 'duplicate')",
            name="ck_inbound_status",
        ),
        Index("ix_inbound_status_next_retry", "status", "next_retry_at"),
        Index("ix_inbound_tenant_received", "tenant_id", "received_at"),
    )


class WazuhRuleTaxonomyMapModel(Base):
    __tablename__ = "wazuh_rule_to_taxonomy_map"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4()),
    )
    tenant_id: Mapped[str | None] = mapped_column(
        String(36), nullable=True, index=True,
    )
    source_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("integration_sources.id", ondelete="CASCADE"),
        nullable=True, index=True,
    )

    match_strategy: Mapped[str] = mapped_column(String(30), nullable=False)
    match_value: Mapped[dict] = mapped_column(JSON, nullable=False)

    taxonomy_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("security_taxonomies.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )

    priority_order: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="100",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true",
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    created_by: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=False,
    )

    __table_args__ = (
        CheckConstraint(
            "match_strategy IN ('rule_id', 'rule_groups_any', 'rule_groups_all', "
            "'level_min', 'level_range')",
            name="ck_wazuh_map_strategy",
        ),
        Index(
            "ix_wazuh_map_tenant_active_priority",
            "tenant_id", "is_active", "priority_order",
        ),
    )
