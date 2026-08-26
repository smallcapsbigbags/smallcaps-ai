from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, Session, mapped_column

from database.models import Base, CompanyRow, utcnow
from product.radar import RadarSetup


class RadarSetupRow(Base):
    __tablename__ = "radar_setups"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    setup_type: Mapped[str] = mapped_column(String(48), nullable=False, index=True)
    setup_score: Mapped[int] = mapped_column(Integer, nullable=False)
    confidence: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="new", nullable=False, index=True)
    headline: Mapped[str] = mapped_column(String(500), nullable=False)
    why_interesting: Mapped[str] = mapped_column(Text, nullable=False)
    next_test: Mapped[str] = mapped_column(Text, default="", nullable=False)
    primary_source_id: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    source_ids: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    evidence: Mapped[list[dict[str, object]]] = mapped_column(JSON, default=list, nullable=False)
    changed_dimensions: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    reaction_gap: Mapped[float | None] = mapped_column(Float, nullable=True)
    radar_version: Mapped[str] = mapped_column(String(64), nullable=False)
    first_detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    last_updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("company_id", "setup_type", name="uq_radar_company_setup_type"),
        Index("ix_radar_status_score", "status", "setup_score"),
    )


class RadarRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def upsert(self, setup: RadarSetup) -> RadarSetupRow:
        company = self.session.query(CompanyRow).filter(CompanyRow.ticker == setup.ticker).one_or_none()
        if company is None:
            raise ValueError(f"Unknown company ticker for radar setup: {setup.ticker}")

        row = (
            self.session.query(RadarSetupRow)
            .filter(
                RadarSetupRow.company_id == company.id,
                RadarSetupRow.setup_type == setup.setup_type,
            )
            .one_or_none()
        )
        if row is None:
            row = RadarSetupRow(
                company_id=company.id,
                setup_type=setup.setup_type,
                setup_score=setup.setup_score,
                confidence=setup.confidence,
                status=setup.status,
                headline=setup.headline,
                why_interesting=setup.why_interesting,
                next_test=setup.next_test,
                primary_source_id=setup.primary_source_id,
                source_ids=list(setup.source_ids),
                evidence=[item.model_dump(mode="json") for item in setup.evidence],
                changed_dimensions=list(setup.changed_dimensions),
                reaction_gap=setup.reaction_gap,
                radar_version=setup.radar_version,
                first_detected_at=setup.first_detected_at or utcnow(),
                last_updated_at=setup.last_updated_at or utcnow(),
            )
            self.session.add(row)
            self.session.flush()
            return row

        row.setup_score = setup.setup_score
        row.confidence = setup.confidence
        if setup.status in {"resolved", "invalidated"}:
            row.status = setup.status
        elif row.status in {"new", "active"}:
            row.status = "active"
        else:
            row.status = setup.status
        row.headline = setup.headline
        row.why_interesting = setup.why_interesting
        row.next_test = setup.next_test
        row.primary_source_id = setup.primary_source_id
        row.source_ids = list(dict.fromkeys([*row.source_ids, *setup.source_ids]))
        row.evidence = [item.model_dump(mode="json") for item in setup.evidence]
        row.changed_dimensions = list(setup.changed_dimensions)
        row.reaction_gap = setup.reaction_gap
        row.radar_version = setup.radar_version
        row.last_updated_at = setup.last_updated_at or utcnow()
        self.session.flush()
        return row

    def active(self, *, limit: int = 20) -> list[RadarSetupRow]:
        return (
            self.session.query(RadarSetupRow)
            .filter(RadarSetupRow.status.in_(["new", "active"]))
            .order_by(RadarSetupRow.setup_score.desc(), RadarSetupRow.last_updated_at.desc())
            .limit(limit)
            .all()
        )

    def mark_inactive(self, *, ticker: str, setup_type: str, status: str) -> RadarSetupRow:
        if status not in {"resolved", "invalidated"}:
            raise ValueError("Radar setup status must be resolved or invalidated")
        row = (
            self.session.query(RadarSetupRow)
            .join(CompanyRow, CompanyRow.id == RadarSetupRow.company_id)
            .filter(CompanyRow.ticker == ticker.upper(), RadarSetupRow.setup_type == setup_type)
            .one()
        )
        row.status = status
        row.last_updated_at = utcnow()
        self.session.flush()
        return row
