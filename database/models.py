from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class CompanyRow(Base):
    __tablename__ = "companies"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ticker: Mapped[str] = mapped_column(String(24), unique=True, nullable=False, index=True)
    company_name: Mapped[str] = mapped_column(String(255), nullable=False)
    isin: Mapped[str] = mapped_column(String(32), default="", nullable=False)
    market: Mapped[str] = mapped_column(String(32), default="AIM", nullable=False)
    sector: Mapped[str] = mapped_column(String(128), default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    announcements: Mapped[list["AnnouncementRow"]] = relationship(back_populates="company")


class AnnouncementRow(Base):
    __tablename__ = "announcements"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_id: Mapped[str] = mapped_column(String(160), unique=True, nullable=False, index=True)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    headline: Mapped[str] = mapped_column(String(500), nullable=False)
    announcement_type: Mapped[str] = mapped_column(String(100), default="Other", nullable=False)
    source_url: Mapped[str] = mapped_column(Text, default="", nullable=False)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    categories: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    company: Mapped[CompanyRow] = relationship(back_populates="announcements")
    analyst_runs: Mapped[list["AnalystRunRow"]] = relationship(back_populates="announcement")


class AnalystRunRow(Base):
    __tablename__ = "analyst_runs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    announcement_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("announcements.id", ondelete="CASCADE"), nullable=False, index=True
    )
    impact_colour: Mapped[str] = mapped_column(String(16), nullable=False)
    impact_score: Mapped[int] = mapped_column(Integer, nullable=False)
    impact_level: Mapped[str] = mapped_column(String(16), nullable=False)
    headline: Mapped[str] = mapped_column(String(500), nullable=False)
    takeaway: Mapped[str] = mapped_column(Text, nullable=False)
    what_changed: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    analyst_view: Mapped[str] = mapped_column(Text, nullable=False)
    supports_case: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    challenges_case: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    watch_items: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    source_warnings: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=0.8, nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(80), nullable=False)
    model_version: Mapped[str] = mapped_column(String(120), nullable=False)
    analysis_version: Mapped[str] = mapped_column(String(120), nullable=False)
    is_current: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)

    announcement: Mapped[AnnouncementRow] = relationship(back_populates="analyst_runs")

    __table_args__ = (
        Index("ix_analyst_runs_announcement_current", "announcement_id", "is_current"),
    )


class FactRow(Base):
    __tablename__ = "facts"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    announcement_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("announcements.id", ondelete="CASCADE"), nullable=False, index=True
    )
    analyst_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("analyst_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    metric: Mapped[str] = mapped_column(String(160), default="", nullable=False, index=True)
    period: Mapped[str] = mapped_column(String(80), default="", nullable=False)
    value: Mapped[str] = mapped_column(String(255), nullable=False)
    unit: Mapped[str] = mapped_column(String(40), default="", nullable=False)
    basis: Mapped[str] = mapped_column(String(32), nullable=False)
    note: Mapped[str] = mapped_column(Text, default="", nullable=False)
    comparator: Mapped[str] = mapped_column(Text, default="", nullable=False)
    previous_value: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    information_status: Mapped[str] = mapped_column(String(32), default="new", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class GuidanceEventRow(Base):
    __tablename__ = "guidance_events"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    announcement_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("announcements.id", ondelete="CASCADE"), nullable=False, index=True
    )
    analyst_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("analyst_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    metric: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    period: Mapped[str] = mapped_column(String(80), default="", nullable=False)
    value: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    comparator: Mapped[str] = mapped_column(Text, default="", nullable=False)
    note: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ManagementClaimRow(Base):
    __tablename__ = "management_claims"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    announcement_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("announcements.id", ondelete="CASCADE"), nullable=False, index=True
    )
    analyst_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("analyst_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    claim: Mapped[str] = mapped_column(Text, nullable=False)
    target_date: Mapped[str] = mapped_column(String(80), default="", nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="open", nullable=False, index=True)
    outcome: Mapped[str] = mapped_column(Text, default="", nullable=False)
    evidence: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class PriceReactionRow(Base):
    __tablename__ = "price_reactions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    announcement_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("announcements.id", ondelete="CASCADE"), nullable=False, index=True
    )
    reaction_session: Mapped[str] = mapped_column(String(32), nullable=False)
    previous_close: Mapped[float | None] = mapped_column(Float, nullable=True)
    open_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    latest_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    close_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    return_1d: Mapped[float | None] = mapped_column(Float, nullable=True)
    return_5d: Mapped[float | None] = mapped_column(Float, nullable=True)
    return_20d: Mapped[float | None] = mapped_column(Float, nullable=True)
    currency: Mapped[str] = mapped_column(String(16), default="GBp", nullable=False)
    source: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    __table_args__ = (
        UniqueConstraint("announcement_id", "reaction_session", name="uq_price_reaction_session"),
    )


class CorrectionRow(Base):
    __tablename__ = "corrections"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    analyst_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("analyst_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    field_path: Mapped[str] = mapped_column(String(255), nullable=False)
    original_value: Mapped[dict[str, object] | list[object] | str | int | float | None] = mapped_column(
        JSON, nullable=True
    )
    corrected_value: Mapped[dict[str, object] | list[object] | str | int | float | None] = mapped_column(
        JSON, nullable=True
    )
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    corrected_by: Mapped[str] = mapped_column(String(120), default="owner", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
