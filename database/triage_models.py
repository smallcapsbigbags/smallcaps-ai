from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, JSON, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from database.models import Base, utcnow


class AnnouncementTriageRow(Base):
    """Durable processing decision for every discovered AIM announcement.

    The triage record is deliberately separate from ``analyst_runs``. ARCHIVE and
    final LIGHT announcements can therefore be retained without manufacturing a
    full Analyst 3.3 note, while FULL/pending rows remain retryable until a current
    analyst run exists.
    """

    __tablename__ = "announcement_triage"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    announcement_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("announcements.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )
    triage_class: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    triage_reason: Mapped[str] = mapped_column(Text, default="", nullable=False)
    processing_level: Mapped[str] = mapped_column(
        String(16), nullable=False, index=True
    )
    triage_version: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    metadata_score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    escalated: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False, index=True
    )
    escalation_reason: Mapped[str] = mapped_column(Text, default="", nullable=False)
    light_facts: Mapped[list[dict[str, object]]] = mapped_column(
        JSON, default=list, nullable=False
    )
    source_hash: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    evidence_hash: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )

    __table_args__ = (
        Index("ix_announcement_triage_level_created", "processing_level", "created_at"),
    )
