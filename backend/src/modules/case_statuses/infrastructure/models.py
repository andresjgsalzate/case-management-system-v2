import uuid
from datetime import datetime, timezone
from sqlalchemy import String, DateTime, Boolean, Integer, JSON
from sqlalchemy.orm import Mapped, mapped_column

from backend.src.core.database import Base


class CaseStatusModel(Base):
    __tablename__ = "case_statuses"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), nullable=False)
    color: Mapped[str] = mapped_column(String(20), nullable=False, default="#6B7280")
    order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_initial: Mapped[bool] = mapped_column(Boolean, default=False)
    is_final: Mapped[bool] = mapped_column(Boolean, default=False)
    pauses_sla: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    allowed_transitions: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
