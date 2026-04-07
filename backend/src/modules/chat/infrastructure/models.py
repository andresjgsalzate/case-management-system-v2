import uuid
from datetime import datetime, timezone
from sqlalchemy import String, DateTime, Boolean, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.src.core.database import Base


class ChatMessageModel(Base):
    __tablename__ = "chat_messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    case_id: Mapped[str] = mapped_column(String(36), ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    tenant_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    # content_type: "text" | "image" | "file"
    content_type: Mapped[str] = mapped_column(String(20), nullable=False, default="text")
    content: Mapped[str] = mapped_column(Text, nullable=False)
    # Si content_type != "text", attachment_id referencia el archivo
    attachment_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("case_attachments.id"), nullable=True)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_edited: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    edits: Mapped[list["ChatMessageEditModel"]] = relationship(
        "ChatMessageEditModel", back_populates="message", lazy="select"
    )


class ChatMessageEditModel(Base):
    __tablename__ = "chat_message_edits"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    message_id: Mapped[str] = mapped_column(String(36), ForeignKey("chat_messages.id", ondelete="CASCADE"), nullable=False, index=True)
    previous_content: Mapped[str] = mapped_column(Text, nullable=False)
    edited_by_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    edited_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    message: Mapped["ChatMessageModel"] = relationship("ChatMessageModel", back_populates="edits")
