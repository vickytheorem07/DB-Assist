"""SQLAlchemy model for storing individual conversation messages."""

from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, DateTime, Identity, Index, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Declarative base for application database models."""


class ConversationHistory(Base):
    """One persisted message in a conversation."""

    __tablename__ = "conversation_messages"
    __table_args__ = (
        CheckConstraint(
            "role IN ('system', 'user', 'assistant', 'tool')",
            name="ck_conversation_messages_role",
        ),
        Index(
            "idx_conversation_messages_conversation_id",
            "conversation_id",
            "message_id",
        ),
    )

    message_id: Mapped[int] = mapped_column(
        BigInteger,
        Identity(always=True),
        primary_key=True,
    )
    conversation_id: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
