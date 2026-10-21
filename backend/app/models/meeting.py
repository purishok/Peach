import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Meeting(Base):
    """A scheduled meeting used by the weekly reporting pipeline."""

    __tablename__ = "meetings"
    __table_args__ = (
        CheckConstraint("length(btrim(title)) > 0", name="ck_meetings_title_not_blank"),
        CheckConstraint("ends_at > starts_at", name="ck_meetings_end_after_start"),
        CheckConstraint("participant_count >= 0", name="ck_meetings_participant_count"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    organizer_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    participant_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    agenda: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    ai_suggestion: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
