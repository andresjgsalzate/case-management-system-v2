import uuid
from datetime import datetime, timezone
from sqlalchemy import String, DateTime, Integer, Text, ForeignKey, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column

from backend.src.core.database import Base


class CaseTransferModel(Base):
    __tablename__ = "case_transfers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("tenants.id"), nullable=True)
    case_id: Mapped[str] = mapped_column(String(36), ForeignKey("cases.id", ondelete="CASCADE"), nullable=False)
    from_user_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    from_level: Mapped[int] = mapped_column(Integer, nullable=False)
    to_user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    to_team_id: Mapped[str] = mapped_column(String(36), ForeignKey("teams.id"), nullable=False)
    to_level: Mapped[int] = mapped_column(Integer, nullable=False)
    transfer_type: Mapped[str] = mapped_column(String(16), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    __table_args__ = (
        CheckConstraint(
            "transfer_type IN ('escalate','reassign','de-escalate')",
            name="transfers_type_valid",
        ),
        CheckConstraint("length(trim(reason)) > 0", name="transfers_reason_nonempty"),
    )
