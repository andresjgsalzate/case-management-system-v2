import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.src.core.database import Base


class AutomationRuleModel(Base):
    """
    Regla: cuando [trigger_event] ocurre y [conditions] se cumplen,
    ejecutar [actions].
    """
    __tablename__ = "automation_rules"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Evento disparador: "case.created" | "case.status_changed" | "sla.breached" | etc.
    trigger_event: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    # JSON array de {field, operator, value}
    conditions: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    # JSON array de {action_type, params}
    actions: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    # "AND" | "OR"
    condition_logic: Mapped[str] = mapped_column(String(5), nullable=False, default="AND")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    execution_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_by_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    tenant_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
