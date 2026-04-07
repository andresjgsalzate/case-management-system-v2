import uuid
from datetime import datetime, timezone
from sqlalchemy import String, DateTime, ForeignKey, JSON, Integer, Boolean
from sqlalchemy.orm import Mapped, mapped_column

from backend.src.core.database import Base


class CaseClassificationModel(Base):
    __tablename__ = "case_classifications"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    case_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    tenant_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    category: Mapped[str | None] = mapped_column(String(200), nullable=True)
    urgency: Mapped[str | None] = mapped_column(String(200), nullable=True)
    area: Mapped[str | None] = mapped_column(String(200), nullable=True)
    complexity_detail: Mapped[str | None] = mapped_column(String(200), nullable=True)
    origin_detail: Mapped[str | None] = mapped_column(String(200), nullable=True)
    classified_by: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    classified_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class ClassificationRuleModel(Base):
    __tablename__ = "classification_rules"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    # conditions: [{"field": "title", "operator": "contains", "value": "urgente"}]
    conditions: Mapped[list] = mapped_column(JSON, default=list)
    # result: {"category": "...", "urgency": "...", ...}
    result: Mapped[dict] = mapped_column(JSON, default=dict)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
