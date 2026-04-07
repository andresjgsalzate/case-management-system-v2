import uuid
from datetime import datetime, timezone
from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.src.core.database import Base


class NotificationModel(Base):
    __tablename__ = "notifications"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    # "case_assigned" | "case_updated" | "sla_breach" | "kb_review_request" | "mention" | "automation" | "info"
    notification_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    reference_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    reference_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    tenant_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
