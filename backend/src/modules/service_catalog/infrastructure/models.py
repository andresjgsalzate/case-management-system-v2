import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.src.core.database import Base


class ServiceCatalogCategoryModel(Base):
    __tablename__ = "service_catalog_categories"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str | None] = mapped_column(
        String(36), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    icon: Mapped[str | None] = mapped_column(String(50), nullable=True)
    color: Mapped[str | None] = mapped_column(String(20), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    items: Mapped[list["ServiceCatalogItemModel"]] = relationship(
        "ServiceCatalogItemModel",
        back_populates="category",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        UniqueConstraint("tenant_id", "slug", name="uq_svc_category_tenant_slug"),
    )


class ServiceCatalogItemModel(Base):
    __tablename__ = "service_catalog_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str | None] = mapped_column(
        String(36), nullable=True, index=True
    )
    category_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("service_catalog_categories.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    default_priority_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("case_priorities.id"), nullable=True
    )
    default_team_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("teams.id"), nullable=True
    )
    default_level: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    sla_policy_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("sla_policies.id"), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    category: Mapped[ServiceCatalogCategoryModel] = relationship(
        "ServiceCatalogCategoryModel", back_populates="items"
    )
    fields: Mapped[list["ServiceCatalogFieldModel"]] = relationship(
        "ServiceCatalogFieldModel",
        back_populates="item",
        cascade="all, delete-orphan",
        order_by="ServiceCatalogFieldModel.sort_order",
    )

    __table_args__ = (
        UniqueConstraint("tenant_id", "slug", name="uq_svc_item_tenant_slug"),
        CheckConstraint("default_level >= 0", name="ck_svc_item_level_non_negative"),
    )


class ServiceCatalogFieldModel(Base):
    __tablename__ = "service_catalog_fields"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str | None] = mapped_column(
        String(36), nullable=True, index=True
    )
    item_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("service_catalog_items.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    field_key: Mapped[str] = mapped_column(String(80), nullable=False)
    label: Mapped[str] = mapped_column(String(200), nullable=False)
    field_type: Mapped[str] = mapped_column(String(20), nullable=False)
    is_required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    placeholder: Mapped[str | None] = mapped_column(String(200), nullable=True)
    help_text: Mapped[str | None] = mapped_column(String(500), nullable=True)
    options: Mapped[list | None] = mapped_column(JSON, nullable=True)
    validation: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    item: Mapped[ServiceCatalogItemModel] = relationship(
        "ServiceCatalogItemModel", back_populates="fields"
    )

    __table_args__ = (
        UniqueConstraint("item_id", "field_key", name="uq_svc_field_item_key"),
        CheckConstraint(
            "field_type IN ('text','textarea','number','date','datetime',"
            "'select','radio','checkbox','multiselect','email','phone')",
            name="ck_svc_field_type_valid",
        ),
    )


class CaseCustomValueModel(Base):
    __tablename__ = "case_custom_values"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str | None] = mapped_column(
        String(36), nullable=True, index=True
    )
    case_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("cases.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    field_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("service_catalog_fields.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    value: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint("case_id", "field_id", name="uq_case_custom_value_case_field"),
    )
