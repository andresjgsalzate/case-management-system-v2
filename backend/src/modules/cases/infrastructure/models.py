import uuid
from datetime import datetime, timezone
from sqlalchemy import String, DateTime, Boolean, Integer, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.src.core.database import Base


class CaseNumberSequenceModel(Base):
    __tablename__ = "case_number_sequences"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str | None] = mapped_column(String(36), nullable=True, unique=True)
    prefix: Mapped[str] = mapped_column(String(4), nullable=False, default="CASE")
    padding: Mapped[int] = mapped_column(Integer, nullable=False, default=4)
    last_number: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class CaseModel(Base):
    __tablename__ = "cases"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    case_number: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, index=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status_id: Mapped[str] = mapped_column(String(36), ForeignKey("case_statuses.id"), nullable=False)
    priority_id: Mapped[str] = mapped_column(String(36), ForeignKey("case_priorities.id"), nullable=False)
    complexity: Mapped[str] = mapped_column(String(20), nullable=False, default="simple")
    application_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("applications.id"), nullable=True)
    origin_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("origins.id"), nullable=True)
    created_by: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    assigned_to: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    team_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("teams.id"), nullable=True)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    archived_by: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    status: Mapped["CaseStatusModel"] = relationship(  # type: ignore[name-defined]
        "CaseStatusModel", foreign_keys=[status_id]
    )
    priority: Mapped["CasePriorityModel"] = relationship(  # type: ignore[name-defined]
        "CasePriorityModel", foreign_keys=[priority_id]
    )
    assignments: Mapped[list["CaseAssignmentModel"]] = relationship(  # type: ignore[name-defined]
        "CaseAssignmentModel", back_populates="case", cascade="all, delete-orphan"
    )
