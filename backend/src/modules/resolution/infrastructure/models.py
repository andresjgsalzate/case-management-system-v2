import uuid
from datetime import datetime, timezone
from sqlalchemy import String, DateTime, SmallInteger, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from backend.src.core.database import Base


class CaseResolutionRequestModel(Base):
    __tablename__ = "case_resolution_requests"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    case_id: Mapped[str] = mapped_column(String(36), ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, index=True)
    tenant_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    chat_message_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("chat_messages.id"), nullable=True)
    requested_by: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    # "pending" | "accepted" | "rejected"
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    responded_by: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rating: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    observation: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Estado en el que estaba el caso justo antes de pasar a "resuelto"
    previous_status_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
