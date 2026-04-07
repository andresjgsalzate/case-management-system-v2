import uuid
from datetime import datetime, timezone
from sqlalchemy import String, DateTime, Boolean, Integer, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.src.core.database import Base


class DispositionCategoryModel(Base):
    __tablename__ = "disposition_categories"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(200), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    tenant_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    dispositions: Mapped[list["DispositionModel"]] = relationship(
        back_populates="category", lazy="select"
    )


class DispositionModel(Base):
    """Texto predefinido de resolución reutilizable."""
    __tablename__ = "dispositions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    category_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("disposition_categories.id"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # Contador de veces que se aplicó esta disposición
    usage_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_by_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=True
    )
    tenant_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    category: Mapped["DispositionCategoryModel"] = relationship(back_populates="dispositions")
