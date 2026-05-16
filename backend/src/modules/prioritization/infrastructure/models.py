"""Sub-spec 03 — Prioritization Engine models.

6 tables:
- prioritization_criteria              — catalog of factors (severity, impact, etc.)
- prioritization_scales                — labels + numeric_value per criterion
- prioritization_formulas              — immutable versioned formulas
- prioritization_formula_criteria      — N:M with weight (sums to 1.00 per formula)
- prioritization_thresholds            — weighted_sum range → case_priority
- case_priority_calculations           — audit of every priority calculation

Multi-tenant: criteria + formulas have `tenant_id NULL` for globals.
Versioning: editing a formula creates a new row with version+1, partial unique
index ensures only ONE active formula per (tenant_id, logical_key).
"""
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from backend.src.core.database import Base


class PrioritizationCriterionModel(Base):
    __tablename__ = "prioritization_criteria"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    tenant_id: Mapped[str | None] = mapped_column(
        String(36), nullable=True, index=True
    )

    code: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # 'taxonomy_field' | 'asset_field' | 'case_custom_value' | 'manual_input' | 'derived'
    data_source: Mapped[str] = mapped_column(String(40), nullable=False)
    source_field_key: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # 'use_default' | 'skip' | 'error'
    missing_data_strategy: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="use_default"
    )
    default_value: Mapped[int | None] = mapped_column(Integer, nullable=True)

    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true"
    )
    sort_order: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        UniqueConstraint("tenant_id", "code", name="uq_criterion_tenant_code"),
        CheckConstraint(
            "data_source IN ('taxonomy_field', 'asset_field', "
            "'case_custom_value', 'manual_input', 'derived')",
            name="ck_criterion_data_source",
        ),
        CheckConstraint(
            "missing_data_strategy IN ('use_default', 'skip', 'error')",
            name="ck_criterion_missing_strategy",
        ),
        CheckConstraint(
            "(missing_data_strategy != 'use_default') OR (default_value IS NOT NULL)",
            name="ck_criterion_default_when_use_default",
        ),
    )


class PrioritizationScaleModel(Base):
    __tablename__ = "prioritization_scales"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    criterion_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("prioritization_criteria.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    label: Mapped[str] = mapped_column(String(50), nullable=False)
    numeric_value: Mapped[int] = mapped_column(Integer, nullable=False)
    color: Mapped[str | None] = mapped_column(String(20), nullable=True)
    sort_order: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )

    __table_args__ = (
        UniqueConstraint(
            "criterion_id", "numeric_value", name="uq_scale_criterion_value"
        ),
    )


class PrioritizationFormulaModel(Base):
    __tablename__ = "prioritization_formulas"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    tenant_id: Mapped[str | None] = mapped_column(
        String(36), nullable=True, index=True
    )

    logical_key: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    version: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="1"
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true"
    )

    effective_from: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    effective_to: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    superseded_by_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("prioritization_formulas.id", ondelete="SET NULL"),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    created_by: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=False
    )

    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "logical_key", "version",
            name="uq_formula_tenant_key_version",
        ),
        # Partial unique index: at most one active formula per (tenant_id, logical_key)
        Index(
            "ux_formula_active",
            "tenant_id", "logical_key",
            unique=True,
            postgresql_where=text("is_active = true"),
        ),
    )


class PrioritizationFormulaCriterionModel(Base):
    __tablename__ = "prioritization_formula_criteria"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    formula_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("prioritization_formulas.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    criterion_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("prioritization_criteria.id", ondelete="RESTRICT"),
        nullable=False, index=True,
    )

    # 0.00 to 1.00 — sum of weights per formula must equal 1.00 (app-validated)
    weight: Mapped[Decimal] = mapped_column(Numeric(3, 2), nullable=False)
    sort_order: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )

    __table_args__ = (
        UniqueConstraint("formula_id", "criterion_id", name="uq_formula_criterion"),
        CheckConstraint(
            "weight > 0 AND weight <= 1",
            name="ck_formula_criterion_weight_range",
        ),
    )


class PrioritizationThresholdModel(Base):
    __tablename__ = "prioritization_thresholds"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    formula_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("prioritization_formulas.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )

    min_value: Mapped[Decimal] = mapped_column(Numeric(4, 2), nullable=False)
    max_value: Mapped[Decimal] = mapped_column(Numeric(4, 2), nullable=False)

    priority_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("case_priorities.id", ondelete="RESTRICT"),
        nullable=False,
    )
    sort_order: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )

    __table_args__ = (
        CheckConstraint(
            "min_value <= max_value", name="ck_threshold_min_le_max"
        ),
        CheckConstraint(
            "min_value >= 0 AND max_value <= 100",
            name="ck_threshold_range",
        ),
    )


class CasePriorityCalculationModel(Base):
    __tablename__ = "case_priority_calculations"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    case_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("cases.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    formula_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("prioritization_formulas.id", ondelete="RESTRICT"),
        nullable=False,
    )
    formula_version: Mapped[int] = mapped_column(Integer, nullable=False)

    inputs: Mapped[dict] = mapped_column(JSON, nullable=False)
    weighted_sum: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    resulting_priority_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("case_priorities.id"), nullable=False
    )

    calculated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False, index=True,
    )

    triggered_by: Mapped[str] = mapped_column(String(40), nullable=False)
    triggered_by_user: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=True
    )

    __table_args__ = (
        Index("ix_calc_case_calculated_at", "case_id", "calculated_at"),
        CheckConstraint(
            "triggered_by IN ('case_created', 'taxonomy_changed', 'asset_changed', "
            "'manual_recalculation', 'formula_promoted')",
            name="ck_calc_triggered_by",
        ),
    )
