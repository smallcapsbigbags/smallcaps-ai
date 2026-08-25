from __future__ import annotations

import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Iterator

from sqlalchemy import JSON, Boolean, DateTime, Index, String, Text, Uuid, select
from sqlalchemy.orm import Mapped, Session, mapped_column, sessionmaker

from analyst.triage import TRIAGE_VERSION, TriageDecision, catalogue_hash, evidence_hash, triage_rns_type
from database.models import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


@contextmanager
def _session_scope(factory: sessionmaker[Session]) -> Iterator[Session]:
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


class AnnouncementTriageRow(Base):
    """Durable newsroom ledger for every discovered AIM catalogue row.

    This table is deliberately independent of ``announcements`` because ARCHIVE
    and LIGHT records may never receive a public AnalystRun. It therefore lets
    Smallcaps.ai record the entire tape without making unanalysed records look
    publication-ready.
    """

    __tablename__ = "announcement_triage"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_id: Mapped[str] = mapped_column(String(160), unique=True, nullable=False, index=True)
    ticker: Mapped[str] = mapped_column(String(24), nullable=False, index=True)
    company_name: Mapped[str] = mapped_column(String(255), nullable=False)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    rns_type: Mapped[str] = mapped_column(String(100), default="Other", nullable=False)
    source_url: Mapped[str] = mapped_column(Text, default="", nullable=False)
    source_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    categories: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)

    triage_class: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    triage_reason: Mapped[str] = mapped_column(Text, default="", nullable=False)
    processing_level: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    triage_version: Mapped[str] = mapped_column(String(80), default=TRIAGE_VERSION, nullable=False)
    escalated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    escalation_reason: Mapped[str] = mapped_column(Text, default="", nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="recorded", nullable=False, index=True)

    light_facts: Mapped[list[dict[str, str]]] = mapped_column(JSON, default=list, nullable=False)
    evidence_status: Mapped[str] = mapped_column(String(32), default="not-retrieved", nullable=False)
    evidence_source_urls: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    evidence_hash: Mapped[str] = mapped_column(String(64), default="", nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    __table_args__ = (
        Index("ix_announcement_triage_level_status", "processing_level", "status"),
        Index("ix_announcement_triage_day", "published_at", "triage_class"),
    )


class TriageRepository:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self.session_factory = session_factory

    def record_catalogue(self, item, decision: TriageDecision) -> None:
        with _session_scope(self.session_factory) as session:
            row = session.scalar(
                select(AnnouncementTriageRow).where(AnnouncementTriageRow.source_id == item.source_id)
            )
            values = {
                "ticker": item.ticker.upper(),
                "company_name": item.company,
                "published_at": item.published_at,
                "title": item.title,
                "rns_type": triage_rns_type(item),
                "source_url": item.source_url,
                "source_hash": catalogue_hash(item),
                "categories": list(getattr(item, "categories", []) or []),
                "triage_class": decision.triage_class,
                "triage_reason": decision.reason,
                "processing_level": decision.processing_level,
                "triage_version": TRIAGE_VERSION,
                "escalated": decision.escalated,
                "escalation_reason": decision.escalation_reason,
                "light_facts": decision.light_facts,
            }
            if row is None:
                session.add(AnnouncementTriageRow(source_id=item.source_id, **values))
            else:
                for key, value in values.items():
                    setattr(row, key, value)

    def record_evidence(self, announcement, decision: TriageDecision, *, status: str) -> None:
        with _session_scope(self.session_factory) as session:
            row = session.scalar(
                select(AnnouncementTriageRow).where(
                    AnnouncementTriageRow.source_id == announcement.source_id
                )
            )
            if row is None:
                raise ValueError(f"Missing triage record for {announcement.source_id}")
            row.triage_class = decision.triage_class
            row.triage_reason = decision.reason
            row.processing_level = decision.processing_level
            row.escalated = decision.escalated
            row.escalation_reason = decision.escalation_reason
            row.light_facts = decision.light_facts
            row.evidence_status = announcement.evidence_status
            row.evidence_source_urls = list(announcement.source_urls)
            row.evidence_hash = evidence_hash(announcement.text, announcement.source_urls)
            row.status = status

    def mark_status(self, source_id: str, status: str) -> None:
        with _session_scope(self.session_factory) as session:
            row = session.scalar(
                select(AnnouncementTriageRow).where(AnnouncementTriageRow.source_id == source_id)
            )
            if row is not None:
                row.status = status

    def completed_source_ids(self, source_ids: list[str]) -> set[str]:
        if not source_ids:
            return set()
        with _session_scope(self.session_factory) as session:
            rows = session.execute(
                select(AnnouncementTriageRow.source_id).where(
                    AnnouncementTriageRow.source_id.in_(source_ids),
                    AnnouncementTriageRow.status == "complete",
                )
            ).scalars().all()
            return set(rows)

    def get(self, source_id: str) -> AnnouncementTriageRow | None:
        with _session_scope(self.session_factory) as session:
            row = session.scalar(
                select(AnnouncementTriageRow).where(AnnouncementTriageRow.source_id == source_id)
            )
            if row is None:
                return None
            session.expunge(row)
            return row
