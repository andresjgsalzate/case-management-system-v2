"""Sub-spec 06 — Operational Center UI models.

1 table:
- integration_health — 30-day rolling per-source 5-minute snapshots
  refreshed every 60s by the operational_center jobs scheduler.

Other rollups (KPIs, severity counters) are computed on-the-fly from
existing tables (`cases`, `case_priority_calculations`, `inbound_events`,
`playbook_runs`, `approval_requests`) — no new persistence needed.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column

from backend.src.core.database import Base


class IntegrationHealthModel(Base):
    __tablename__ = "integration_health"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4()),
    )
    source_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("integration_sources.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False, index=True,
    )
    events_received_5min: Mapped[int] = mapped_column(Integer, nullable=False)
    events_processed_5min: Mapped[int] = mapped_column(Integer, nullable=False)
    events_failed_5min: Mapped[int] = mapped_column(Integer, nullable=False)
    avg_latency_ms_5min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    extra_metrics: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    __table_args__ = (
        Index(
            "ix_int_health_source_recorded",
            "source_id", "recorded_at",
        ),
        CheckConstraint(
            "status IN ('healthy', 'degraded', 'down')",
            name="ck_int_health_status",
        ),
    )
