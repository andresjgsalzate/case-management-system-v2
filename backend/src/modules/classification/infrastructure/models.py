import uuid
from datetime import datetime, timezone
from sqlalchemy import String, DateTime, ForeignKey, JSON, Integer, Boolean, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from backend.src.core.database import Base


class ClassificationCriterionModel(Base):
    """Criterio configurable de la rúbrica de clasificación."""
    __tablename__ = "classification_criteria"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    score1_description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    score2_description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    score3_description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class ClassificationThresholdModel(Base):
    """Umbrales para convertir el puntaje total en nivel de complejidad."""
    __tablename__ = "classification_thresholds"

    __table_args__ = (UniqueConstraint("tenant_id", name="uq_classification_thresholds_tenant"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    # 1-low_max = BAJA; (low_max+1)-medium_max = MEDIA; >medium_max = ALTA
    low_max: Mapped[int] = mapped_column(Integer, nullable=False, default=6)
    medium_max: Mapped[int] = mapped_column(Integer, nullable=False, default=11)


class CaseClassificationModel(Base):
    """Resultado de clasificación de un caso usando la rúbrica de puntos."""
    __tablename__ = "case_classifications"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    case_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    tenant_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    # {criterion_id: 1|2|3}
    scores: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    total_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    complexity_level: Mapped[str | None] = mapped_column(String(10), nullable=True)  # baja|media|alta
    classified_by: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    classified_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class ClassificationRuleModel(Base):
    __tablename__ = "classification_rules"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    conditions: Mapped[list] = mapped_column(JSON, default=list)
    result: Mapped[dict] = mapped_column(JSON, default=dict)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
