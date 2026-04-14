import uuid
from datetime import datetime, timezone
from sqlalchemy import String, DateTime, Boolean, Integer, Float, ForeignKey, JSON, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from backend.src.core.database import Base


class SLAPolicyModel(Base):
    __tablename__ = "sla_policies"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    priority_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("case_priorities.id"), nullable=False
    )
    target_resolution_hours: Mapped[float] = mapped_column(Float, nullable=False)


class SLARecordModel(Base):
    __tablename__ = "sla_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    case_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    policy_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("sla_policies.id"), nullable=False
    )
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    target_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    breached_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    escalated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_breached: Mapped[bool] = mapped_column(Boolean, default=False)
    is_escalated: Mapped[bool] = mapped_column(Boolean, default=False)
    paused_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status_paused_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    total_paused_seconds: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0", default=0)


class SLAHolidayModel(Base):
    __tablename__ = "sla_holidays"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    description: Mapped[str] = mapped_column(String(200), nullable=False)
    is_recurring: Mapped[bool] = mapped_column(Boolean, default=False)
    created_by: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class SLAWorkScheduleModel(Base):
    __tablename__ = "sla_work_schedules"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str | None] = mapped_column(String(36), nullable=True, unique=True)
    # [0,1,2,3,4] = lun-vie; 0=lunes, 6=domingo
    work_days: Mapped[list] = mapped_column(JSON, default=lambda: [0, 1, 2, 3, 4])
    work_start_time: Mapped[str] = mapped_column(String(5), nullable=False, default="00:00")
    work_end_time: Mapped[str] = mapped_column(String(5), nullable=False, default="23:59")


class SLAIntegrationConfigModel(Base):
    __tablename__ = "sla_integration_config"
    __table_args__ = (UniqueConstraint("tenant_id", name="uq_sla_integration_config_tenant"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, unique=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    pause_on_timer: Mapped[bool] = mapped_column(Boolean, default=True)
    low_max_hours: Mapped[float | None] = mapped_column(Float, nullable=True)
    medium_max_hours: Mapped[float | None] = mapped_column(Float, nullable=True)
    high_max_hours: Mapped[float | None] = mapped_column(Float, nullable=True)
