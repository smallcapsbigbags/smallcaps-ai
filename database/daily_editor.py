from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, time, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from analyst.evidence import dedupe_source_urls
from analyst.monitoring_sheet import (
    monitoring_outlook_from_statuses,
    monitoring_signal_from_colour,
)
from database.db import session_scope
from database.models import AnalystRunRow, AnnouncementRow, CompanyRow, GuidanceEventRow
from product.daily_editor import DailyEditorCandidate, DailyEditorPage, build_daily_editor

LONDON = ZoneInfo("Europe/London")


class DailyEditorRepository:
    """Read-only newsroom projection over publication-safe FULL analyses.

    ARCHIVE and LIGHT records never become editorial candidates because Pass 6 does
    not create an AnalystRun for them. Historical deterministic metadata notes are
    explicitly excluded so the editor can safely replay pre-Pass-6 market days.
    """

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self.session_factory = session_factory

    def get_edition(self, day: date, *, cutoff: time) -> DailyEditorPage:
        start = datetime.combine(day, time.min, tzinfo=LONDON).astimezone(timezone.utc)
        end = datetime.combine(day, cutoff, tzinfo=LONDON).astimezone(timezone.utc)
        if end <= start:
            raise ValueError("cutoff must be after 00:00 Europe/London")

        with session_scope(self.session_factory) as session:
            records = session.execute(
                select(AnnouncementRow, CompanyRow, AnalystRunRow)
                .join(CompanyRow, CompanyRow.id == AnnouncementRow.company_id)
                .join(
                    AnalystRunRow,
                    AnalystRunRow.announcement_id == AnnouncementRow.id,
                )
                .where(
                    AnnouncementRow.published_at >= start,
                    AnnouncementRow.published_at < end,
                    AnalystRunRow.is_current.is_(True),
                    AnalystRunRow.quality_status == "publishable",
                    ~AnalystRunRow.model_version.like("deterministic-metadata%"),
                )
            ).all()

            run_ids = [run.id for _announcement, _company, run in records]
            guidance_by_run: dict[object, list[str]] = defaultdict(list)
            if run_ids:
                guidance_rows = session.scalars(
                    select(GuidanceEventRow)
                    .where(GuidanceEventRow.analyst_run_id.in_(run_ids))
                    .order_by(
                        GuidanceEventRow.analyst_run_id,
                        GuidanceEventRow.ordinal,
                        GuidanceEventRow.created_at,
                    )
                ).all()
                for item in guidance_rows:
                    guidance_by_run[item.analyst_run_id].append(str(item.status or ""))

            candidates = [
                self._candidate(
                    announcement=announcement,
                    company=company,
                    run=run,
                    guidance_statuses=guidance_by_run.get(run.id, []),
                )
                for announcement, company, run in records
            ]

        return build_daily_editor(day=day, cutoff=cutoff, candidates=candidates)

    @staticmethod
    def _candidate(
        *,
        announcement: AnnouncementRow,
        company: CompanyRow,
        run: AnalystRunRow,
        guidance_statuses: list[str],
    ) -> DailyEditorCandidate:
        source_urls = dedupe_source_urls(
            announcement.source_urls,
            announcement.source_url,
            run.source_references,
        )
        what_changed = dict(run.what_changed or {})
        return DailyEditorCandidate(
            source_id=announcement.source_id,
            ticker=company.ticker,
            company=company.company_name,
            published_at=_as_london(announcement.published_at),
            rns_title=announcement.headline,
            rns_type=announcement.announcement_type,
            impact_score=run.impact_score,
            impact_level=run.impact_level,  # type: ignore[arg-type]
            signal=monitoring_signal_from_colour(run.impact_colour),
            outlook=monitoring_outlook_from_statuses(guidance_statuses),
            verdict=run.headline,
            what_changed=str(what_changed.get("today") or run.takeaway or ""),
            analyst_view=run.analyst_view,
            source_url=source_urls[0] if source_urls else "",
            analysis_version=run.analysis_version,
            prompt_version=run.prompt_version,
            model_version=run.model_version,
            guidance_statuses=[item for item in guidance_statuses if item],
        )


def _as_london(value: datetime) -> datetime:
    parsed = value
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(LONDON)
