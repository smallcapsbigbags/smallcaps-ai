from __future__ import annotations

import uuid
from datetime import date, datetime, time, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, JSON, String, Text, Uuid, desc, or_, select, update
from sqlalchemy.orm import Mapped, Session, mapped_column, sessionmaker

from database.models import AnalystRunRow, AnnouncementRow, Base, CompanyRow, utcnow
from product.daily_editor import (
    AlgorithmicBucket,
    DailyEditorOverride,
    EditorialOverrideAction,
    demoted_bucket,
    editorial_story_family,
    make_story_key,
    promoted_bucket,
    story_family_window_days,
)

LONDON = ZoneInfo("Europe/London")
_RANK_ACTIONS = {"lead", "promote", "demote", "suppress"}


class EditorialStoryLinkRow(Base):
    __tablename__ = "editorial_story_links"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    announcement_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("announcements.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    story_key: Mapped[str] = mapped_column(String(220), nullable=False, index=True)
    story_family: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    linked_by: Mapped[str] = mapped_column(String(32), default="deterministic", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    __table_args__ = (
        Index("ix_editorial_story_company_family", "company_id", "story_family"),
    )


class EditorialOverrideRow(Base):
    __tablename__ = "editorial_overrides"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    edition_date: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    edition_state: Mapped[str] = mapped_column(String(24), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    source_id: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    target_source_id: Mapped[str] = mapped_column(String(160), default="", nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    algorithm_score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    algorithm_bucket: Mapped[str] = mapped_column(String(24), default="suppressed", nullable=False)
    algorithm_story_key: Mapped[str] = mapped_column(String(220), default="", nullable=False)
    created_by: Mapped[str] = mapped_column(String(120), default="owner", nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    __table_args__ = (
        Index("ix_editorial_override_scope", "edition_date", "edition_state", "active"),
    )


class EditorialCalibrationCaseRow(Base):
    __tablename__ = "editorial_calibration_cases"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    override_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("editorial_overrides.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    case_key: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    edition_date: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    edition_state: Mapped[str] = mapped_column(String(24), nullable=False, index=True)
    source_id: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(16), nullable=False)
    expected_bucket: Mapped[str] = mapped_column(String(24), nullable=False)
    algorithm_score: Mapped[int] = mapped_column(Integer, nullable=False)
    algorithm_bucket: Mapped[str] = mapped_column(String(24), nullable=False)
    story_key: Mapped[str] = mapped_column(String(220), default="", nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class EditorialCalibrationRepository:
    """Persistent newsroom memory for story identity and owner calibration."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self.session_factory = session_factory

    def ensure_story_links(self, day: date, *, cutoff: time = time(23, 59, 59)) -> int:
        start = datetime.combine(day, time.min, tzinfo=LONDON).astimezone(timezone.utc)
        end = datetime.combine(day, cutoff, tzinfo=LONDON).astimezone(timezone.utc)
        if end <= start:
            raise ValueError("cutoff must be after 00:00 Europe/London")

        created = 0
        with self.session_factory() as session:
            records = session.execute(
                select(AnnouncementRow, CompanyRow)
                .join(CompanyRow, CompanyRow.id == AnnouncementRow.company_id)
                .join(AnalystRunRow, AnalystRunRow.announcement_id == AnnouncementRow.id)
                .where(
                    AnnouncementRow.published_at >= start,
                    AnnouncementRow.published_at < end,
                    AnalystRunRow.is_current.is_(True),
                    AnalystRunRow.quality_status == "publishable",
                    ~AnalystRunRow.model_version.like("deterministic-metadata%"),
                )
                .order_by(AnnouncementRow.published_at, AnnouncementRow.source_id)
            ).all()

            for announcement, company in records:
                existing = session.scalar(
                    select(EditorialStoryLinkRow).where(
                        EditorialStoryLinkRow.announcement_id == announcement.id
                    )
                )
                if existing is not None:
                    continue

                family = editorial_story_family(
                    announcement.announcement_type,
                    announcement.headline,
                )
                published = _aware_utc(announcement.published_at)
                lookback = published - timedelta(days=story_family_window_days(family))
                prior = session.execute(
                    select(EditorialStoryLinkRow, AnnouncementRow)
                    .join(
                        AnnouncementRow,
                        AnnouncementRow.id == EditorialStoryLinkRow.announcement_id,
                    )
                    .where(
                        EditorialStoryLinkRow.company_id == company.id,
                        EditorialStoryLinkRow.story_family == family,
                        AnnouncementRow.published_at < published,
                        AnnouncementRow.published_at >= lookback,
                    )
                    .order_by(desc(AnnouncementRow.published_at))
                    .limit(1)
                ).first()
                story_key = (
                    prior[0].story_key
                    if prior is not None
                    else make_story_key(company.ticker, family, announcement.source_id)
                )
                session.add(
                    EditorialStoryLinkRow(
                        announcement_id=announcement.id,
                        company_id=company.id,
                        story_key=story_key,
                        story_family=family,
                        linked_by="deterministic",
                    )
                )
                session.flush()
                created += 1

            session.commit()
        return created

    def links_for_source_ids(self, source_ids: list[str]) -> dict[str, tuple[str, str]]:
        clean_ids = list(dict.fromkeys(item.strip() for item in source_ids if item.strip()))
        if not clean_ids:
            return {}
        with self.session_factory() as session:
            rows = session.execute(
                select(AnnouncementRow.source_id, EditorialStoryLinkRow)
                .join(
                    EditorialStoryLinkRow,
                    EditorialStoryLinkRow.announcement_id == AnnouncementRow.id,
                )
                .where(AnnouncementRow.source_id.in_(clean_ids))
            ).all()
        return {
            source_id: (link.story_key, link.story_family)
            for source_id, link in rows
        }

    def active_overrides(self, day: date, edition_state: str) -> list[DailyEditorOverride]:
        state = edition_state.strip().lower()
        with self.session_factory() as session:
            rows = session.scalars(
                select(EditorialOverrideRow)
                .where(
                    EditorialOverrideRow.edition_date == day.isoformat(),
                    EditorialOverrideRow.active.is_(True),
                    or_(
                        EditorialOverrideRow.edition_state == state,
                        EditorialOverrideRow.edition_state == "all",
                    ),
                )
                .order_by(EditorialOverrideRow.created_at, EditorialOverrideRow.id)
            ).all()
        return [
            DailyEditorOverride(
                source_id=row.source_id,
                action=row.action,  # type: ignore[arg-type]
                target_source_id=row.target_source_id,
                reason=row.reason,
                algorithm_score=row.algorithm_score,
                algorithm_bucket=row.algorithm_bucket,  # type: ignore[arg-type]
                algorithm_story_key=row.algorithm_story_key,
                created_at=row.created_at,
            )
            for row in rows
        ]

    def record_override(
        self,
        *,
        day: date,
        edition_state: str,
        action: EditorialOverrideAction,
        source_id: str,
        target_source_id: str = "",
        reason: str,
        algorithm_score: int,
        algorithm_bucket: AlgorithmicBucket,
        algorithm_story_key: str,
        snapshot: dict[str, Any] | None = None,
        created_by: str = "owner",
    ) -> dict[str, Any]:
        clean_source = source_id.strip()
        clean_target = target_source_id.strip()
        clean_reason = " ".join(reason.strip().split())
        clean_state = edition_state.strip().lower()
        if not clean_source:
            raise ValueError("source_id is required")
        if not clean_reason:
            raise ValueError("reason is required")
        if clean_state not in {"early_read", "morning_note", "aim_close", "custom", "all"}:
            raise ValueError("unsupported edition_state")
        if action == "group" and not clean_target:
            raise ValueError("group override requires target_source_id")
        if action != "group" and clean_target:
            raise ValueError("target_source_id is only valid for group overrides")

        stored_state = "all" if action == "group" else clean_state
        with self.session_factory() as session:
            if action == "lead":
                session.execute(
                    update(EditorialOverrideRow)
                    .where(
                        EditorialOverrideRow.edition_date == day.isoformat(),
                        EditorialOverrideRow.edition_state == stored_state,
                        EditorialOverrideRow.action == "lead",
                        EditorialOverrideRow.active.is_(True),
                    )
                    .values(active=False)
                )

            if action in _RANK_ACTIONS:
                session.execute(
                    update(EditorialOverrideRow)
                    .where(
                        EditorialOverrideRow.edition_date == day.isoformat(),
                        EditorialOverrideRow.edition_state == stored_state,
                        EditorialOverrideRow.source_id == clean_source,
                        EditorialOverrideRow.action.in_(sorted(_RANK_ACTIONS)),
                        EditorialOverrideRow.active.is_(True),
                    )
                    .values(active=False)
                )
            else:
                session.execute(
                    update(EditorialOverrideRow)
                    .where(
                        EditorialOverrideRow.edition_date == day.isoformat(),
                        EditorialOverrideRow.source_id == clean_source,
                        EditorialOverrideRow.action == "group",
                        EditorialOverrideRow.active.is_(True),
                    )
                    .values(active=False)
                )

            if action == "group":
                source_link = _link_for_source(session, clean_source)
                target_link = _link_for_source(session, clean_target)
                if source_link is None or target_link is None:
                    raise ValueError("group override requires both announcements to have story links")
                source_link.story_key = target_link.story_key
                source_link.story_family = target_link.story_family
                source_link.linked_by = "owner"
                algorithm_story_key = target_link.story_key

            row = EditorialOverrideRow(
                edition_date=day.isoformat(),
                edition_state=stored_state,
                action=action,
                source_id=clean_source,
                target_source_id=clean_target,
                reason=clean_reason,
                algorithm_score=max(0, int(algorithm_score)),
                algorithm_bucket=algorithm_bucket,
                algorithm_story_key=algorithm_story_key,
                created_by=created_by.strip() or "owner",
                active=True,
            )
            session.add(row)
            session.flush()

            expected_bucket = _expected_bucket(action, algorithm_bucket)
            case_key = f"{day.isoformat()}:{stored_state}:{clean_source}:{row.id}"
            calibration = EditorialCalibrationCaseRow(
                override_id=row.id,
                case_key=case_key,
                edition_date=day.isoformat(),
                edition_state=stored_state,
                source_id=clean_source,
                action=action,
                expected_bucket=expected_bucket,
                algorithm_score=row.algorithm_score,
                algorithm_bucket=algorithm_bucket,
                story_key=algorithm_story_key,
                reason=clean_reason,
                snapshot=dict(snapshot or {}),
            )
            session.add(calibration)
            session.commit()
            return {
                "override_id": str(row.id),
                "case_key": case_key,
                "edition_date": day.isoformat(),
                "edition_state": stored_state,
                "action": action,
                "source_id": clean_source,
                "target_source_id": clean_target,
                "algorithm_score": row.algorithm_score,
                "algorithm_bucket": algorithm_bucket,
                "expected_bucket": expected_bucket,
                "story_key": algorithm_story_key,
            }

    def calibration_cases(self) -> list[dict[str, Any]]:
        with self.session_factory() as session:
            rows = session.scalars(
                select(EditorialCalibrationCaseRow).order_by(
                    EditorialCalibrationCaseRow.created_at,
                    EditorialCalibrationCaseRow.id,
                )
            ).all()
        return [
            {
                "case_key": row.case_key,
                "edition_date": row.edition_date,
                "edition_state": row.edition_state,
                "source_id": row.source_id,
                "action": row.action,
                "expected_bucket": row.expected_bucket,
                "algorithm_score": row.algorithm_score,
                "algorithm_bucket": row.algorithm_bucket,
                "story_key": row.story_key,
                "reason": row.reason,
                "snapshot": dict(row.snapshot or {}),
                "created_at": row.created_at.isoformat(),
            }
            for row in rows
        ]


def _expected_bucket(
    action: EditorialOverrideAction,
    algorithm_bucket: AlgorithmicBucket,
) -> str:
    if action == "lead":
        return "lead"
    if action == "promote":
        return promoted_bucket(algorithm_bucket)
    if action == "demote":
        return demoted_bucket(algorithm_bucket)
    if action == "suppress":
        return "suppressed"
    return algorithm_bucket


def _link_for_source(session: Session, source_id: str) -> EditorialStoryLinkRow | None:
    return session.scalar(
        select(EditorialStoryLinkRow)
        .join(AnnouncementRow, AnnouncementRow.id == EditorialStoryLinkRow.announcement_id)
        .where(AnnouncementRow.source_id == source_id)
    )


def _aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
