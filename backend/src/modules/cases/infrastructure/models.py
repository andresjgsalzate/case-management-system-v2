import uuid
from datetime import datetime, timezone
from sqlalchemy import String, DateTime, Boolean, Integer, Text, ForeignKey, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.src.core.database import Base


class CaseNumberSequenceModel(Base):
    """Legacy — kept for migration compatibility. Use CaseNumberRangeModel instead."""
    __tablename__ = "case_number_sequences"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str | None] = mapped_column(String(36), nullable=True, unique=True)
    prefix: Mapped[str] = mapped_column(String(4), nullable=False, default="CASE")
    padding: Mapped[int] = mapped_column(Integer, nullable=False, default=4)
    last_number: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class CaseNumberRangeModel(Base):
    """
    Defines a numbered range for a prefix (e.g. REQ 000001–200000).
    Multiple consecutive ranges can exist per prefix+tenant.
    The active range is the first non-exhausted one (ordered by range_start).
    """
    __tablename__ = "case_number_ranges"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    prefix: Mapped[str] = mapped_column(String(4), nullable=False)
    range_start: Mapped[int] = mapped_column(Integer, nullable=False)
    range_end: Mapped[int] = mapped_column(Integer, nullable=False)
    # current_number starts at range_start - 1 (no number generated yet).
    # When current_number == range_end the range is exhausted.
    current_number: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


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
    current_level: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default=text("1")
    )
    application_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("applications.id"), nullable=True)
    origin_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("origins.id"), nullable=True)
    created_by: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    assigned_to: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    team_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("teams.id"), nullable=True)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    archived_by: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    solution_description: Mapped[str | None] = mapped_column(Text, nullable=True)
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
    application: Mapped["ApplicationModel"] = relationship(  # type: ignore[name-defined]
        "ApplicationModel", foreign_keys=[application_id]
    )
    origin: Mapped["OriginModel"] = relationship(  # type: ignore[name-defined]
        "OriginModel", foreign_keys=[origin_id]
    )
    assignments: Mapped[list["CaseAssignmentModel"]] = relationship(  # type: ignore[name-defined]
        "CaseAssignmentModel", back_populates="case", cascade="all, delete-orphan"
    )
    assigned_user: Mapped["UserModel | None"] = relationship(  # type: ignore[name-defined]
        "UserModel", foreign_keys=[assigned_to]
    )
