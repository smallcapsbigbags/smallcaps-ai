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
from database.editorial_calibration import EditorialCalibrationRepository
from database.models import AnalystRunRow, AnnouncementRow, CompanyRow, GuidanceEventRow
from product.daily_editor import (
    CANONICAL_EDITION_CUTOFFS,
    DailyEditorCandidate,
    DailyEditorPage,
    DailyEditorTimeline,
    algorithmic_bucket_for_score,
    build_daily_editor,
    build_daily_editor_timeline,
    editorial_priority,
    editorial_story_family,
    make_story_key,
    resolve_editor_cutoff,
)

LONDON = ZoneInfo("Europe/London")


class DailyEditorRepository:
    """Newsroom projection over publication-safe FULL analyses.

    Pass 8 keeps the public read model deterministic while adding canonical edition
    states, persistent developing-story keys and owner calibration overrides. ARCHIVE,
    LIGHT and review-state records remain outside the editor.
    """

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self.session_factory = session_factory
        self.calibration = EditorialCalibrationRepository(session_factory)

    def get_edition(
        self,
        day: date,
        *,
        cutoff: time | None = None,
        edition_state: str | None = None,
        apply_overrides: bool = True,
    ) -> DailyEditorPage:
        state, resolved_cutoff = resolve_editor_cutoff(
            edition_state=edition_state,
            cutoff=cutoff,
        )
        candidates = self._load_candidates(day, cutoff=resolved_cutoff)
        overrides = (
            self.calibration.active_overrides(day, state)
            if apply_overrides
            else []
        )
        return build_daily_editor(
            day=day,
            edition_state=state if state != "custom" else None,
            cutoff=resolved_cutoff if state == "custom" else None,
            candidates=candidates,
            overrides=overrides,
        )

    def get_timeline(self, day: date, *, apply_overrides: bool = True) -> DailyEditorTimeline:
        editions = [
            self.get_edition(
                day,
                edition_state=state,
                apply_overrides=apply_overrides,
            )
            for state in ("early_read", "morning_note", "aim_close")
        ]
        return build_daily_editor_timeline(day=day, editions=editions)

    def algorithm_snapshot(
        self,
        day: date,
        *,
        source_id: str,
        edition_state: str,
    ) -> dict[str, object]:
        state, cutoff = resolve_editor_cutoff(edition_state=edition_state)
        candidates = self._load_candidates(day, cutoff=cutoff)
        candidate = next(
            (item for item in candidates if item.source_id == source_id.strip()),
            None,
        )
        if candidate is None:
            raise ValueError("source_id is not a publication-safe FULL candidate in this edition")
        score, reasons = editorial_priority(candidate)
        family = candidate.story_family or editorial_story_family(
            candidate.rns_type,
            candidate.rns_title,
        )
        story_key = candidate.story_key or make_story_key(
            candidate.ticker,
            family,
            candidate.source_id,
        )
        return {
            "edition_state": state,
            "cutoff": cutoff.strftime("%H:%M"),
            "source_id": candidate.source_id,
            "ticker": candidate.ticker,
            "company": candidate.company,
            "rns_title": candidate.rns_title,
            "rns_type": candidate.rns_type,
            "story_key": story_key,
            "story_family": family,
            "algorithm_score": score,
            "algorithm_bucket": algorithmic_bucket_for_score(score),
            "ranking_reasons": reasons,
            "impact_score": candidate.impact_score,
            "signal": candidate.signal,
            "outlook": candidate.outlook,
        }

    def _load_candidates(self, day: date, *, cutoff: time) -> list[DailyEditorCandidate]:
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
                .order_by(AnnouncementRow.published_at, AnnouncementRow.source_id)
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

            raw = [
                (
                    announcement,
                    company,
                    run,
                    guidance_by_run.get(run.id, []),
                )
                for announcement, company, run in records
            ]

        links = self.calibration.links_for_source_ids(
            [announcement.source_id for announcement, _company, _run, _guidance in raw]
        )
        return [
            self._candidate(
                announcement=announcement,
                company=company,
                run=run,
                guidance_statuses=guidance_statuses,
                story_link=links.get(announcement.source_id),
            )
            for announcement, company, run, guidance_statuses in raw
        ]

    @staticmethod
    def _candidate(
        *,
        announcement: AnnouncementRow,
        company: CompanyRow,
        run: AnalystRunRow,
        guidance_statuses: list[str],
        story_link: tuple[str, str] | None = None,
    ) -> DailyEditorCandidate:
        source_urls = dedupe_source_urls(
            announcement.source_urls,
            announcement.source_url,
            run.source_references,
        )
        what_changed = dict(run.what_changed or {})
        family = editorial_story_family(
            announcement.announcement_type,
            announcement.headline,
        )
        story_key, story_family = story_link or ("", family)
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
            story_key=story_key,
            story_family=story_family,
        )


def canonical_cutoffs() -> dict[str, str]:
    return {
        state: cutoff.strftime("%H:%M")
        for state, cutoff in CANONICAL_EDITION_CUTOFFS.items()
    }


def _as_london(value: datetime) -> datetime:
    parsed = value
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(LONDON)
