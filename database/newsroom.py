from __future__ import annotations

import re
from collections import defaultdict
from datetime import date, datetime, time, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from database.daily_editor import DailyEditorRepository
from database.db import session_scope
from database.models import (
    AnalystRunRow,
    AnnouncementRow,
    CompanyRow,
    FactRow,
    GuidanceEventRow,
    ManagementClaimRow,
)
from product.daily_editor import DailyEditorStory
from product.newsroom import (
    NewsroomEdition,
    NewsroomFact,
    NewsroomGuidance,
    NewsroomMetricHistory,
    NewsroomNumberPoint,
    NewsroomStoryPacket,
    build_newsroom_edition,
)

LONDON = ZoneInfo("Europe/London")


def _clean(value: object) -> str:
    return " ".join(str(value or "").strip().split())


def _normal(value: object) -> str:
    return " ".join(re.sub(r"[^a-z0-9]+", " ", _clean(value).lower()).split())


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _iso(value: datetime) -> str:
    return _aware(value).isoformat()


def _period_family(period: object, as_of_date: object) -> str:
    if _clean(as_of_date):
        return "point-in-time"
    text = _normal(period)
    if re.search(r"\bh1\b", text) or "first half" in text:
        return "h1"
    if re.search(r"\bh2\b", text) or "second half" in text:
        return "h2"
    quarter = re.search(r"\bq([1-4])\b", text)
    if quarter:
        return f"q{quarter.group(1)}"
    if "six months" in text or "half year" in text:
        return "half-year"
    if re.search(r"\bfy\s*\d{2,4}\b", text) or "full year" in text or "year ended" in text:
        return "fy"
    return text or "point-in-time"


def _series_key(fact: FactRow) -> tuple[str, str, str, str, str]:
    return (
        _normal(fact.metric or fact.label),
        _period_family(fact.period, fact.as_of_date),
        _normal(fact.unit),
        _normal(fact.currency),
        _normal(fact.basis),
    )


def _direction(values: list[float | None]) -> str:
    numeric = [value for value in values if value is not None]
    if len(numeric) < 2:
        return "unclear"
    previous, latest = numeric[-2], numeric[-1]
    tolerance = max(abs(previous), 1.0) * 1e-9
    if abs(latest - previous) <= tolerance:
        return "flat"
    return "up" if latest > previous else "down"


class NewsroomRepository:
    """Evidence-bound newsroom projection over the Pass 8 editor.

    This layer does not call an LLM. It turns publication-safe Analyst 3.3 work
    plus structured Company Memory rows into a journalistic article contract,
    then runs the deterministic copy desk in product.newsroom.
    """

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self.session_factory = session_factory
        self.editor = DailyEditorRepository(session_factory)

    def get_edition(
        self,
        day: date,
        *,
        cutoff: time | None = None,
        edition_state: str | None = None,
        apply_overrides: bool = True,
    ) -> NewsroomEdition:
        page = self.editor.get_edition(
            day,
            cutoff=cutoff,
            edition_state=edition_state,
            apply_overrides=apply_overrides,
        )
        stories = [
            *([page.lead] if page.lead is not None else []),
            *page.also_matters,
            *page.quick_takes,
        ]
        packets = [self._packet(story) for story in stories]
        return build_newsroom_edition(editor_page=page, packets=packets)

    def _packet(self, story: DailyEditorStory) -> NewsroomStoryPacket:
        source_ids = list(dict.fromkeys(story.source_ids or [story.primary_source_id]))
        with session_scope(self.session_factory) as session:
            records = session.execute(
                select(AnnouncementRow, CompanyRow, AnalystRunRow)
                .join(CompanyRow, CompanyRow.id == AnnouncementRow.company_id)
                .join(AnalystRunRow, AnalystRunRow.announcement_id == AnnouncementRow.id)
                .where(
                    AnnouncementRow.source_id.in_(source_ids),
                    AnalystRunRow.is_current.is_(True),
                    AnalystRunRow.quality_status == "publishable",
                    ~AnalystRunRow.model_version.like("deterministic-metadata%"),
                )
                .order_by(AnnouncementRow.published_at, AnnouncementRow.source_id)
            ).all()
            if not records:
                raise ValueError(f"No publication-safe Analyst 3.3 evidence for story {story.story_key}")

            by_source = {
                announcement.source_id: (announcement, company, run)
                for announcement, company, run in records
            }
            primary = by_source.get(story.primary_source_id)
            if primary is None:
                primary = max(records, key=lambda item: (_aware(item[0].published_at), item[0].source_id))
            _primary_announcement, primary_company, primary_run = primary
            company_id = primary_company.id
            latest_at = max(_aware(announcement.published_at) for announcement, _company, _run in records)

            source_urls = {
                announcement.source_id: _clean(announcement.source_url)
                for announcement, _company, _run in records
            }
            source_published = {
                announcement.source_id: _iso(announcement.published_at)
                for announcement, _company, _run in records
            }
            source_by_announcement_id = {
                announcement.id: announcement.source_id
                for announcement, _company, _run in records
            }

            announcement_ids = list(source_by_announcement_id)
            fact_rows = session.scalars(
                select(FactRow)
                .where(FactRow.announcement_id.in_(announcement_ids))
                .order_by(FactRow.created_at, FactRow.ordinal)
            ).all()
            guidance_rows = session.scalars(
                select(GuidanceEventRow)
                .where(GuidanceEventRow.announcement_id.in_(announcement_ids))
                .order_by(GuidanceEventRow.created_at, GuidanceEventRow.ordinal)
            ).all()

            comparator_ids = {
                _clean(item.comparator_source_id)
                for item in fact_rows
                if _clean(item.comparator_source_id)
            } | {
                _clean(item.previous_source_id)
                for item in guidance_rows
                if _clean(item.previous_source_id)
            }
            if comparator_ids:
                comparator_rows = session.scalars(
                    select(AnnouncementRow).where(AnnouncementRow.source_id.in_(sorted(comparator_ids)))
                ).all()
                for announcement in comparator_rows:
                    source_urls.setdefault(announcement.source_id, _clean(announcement.source_url))
                    source_published.setdefault(announcement.source_id, _iso(announcement.published_at))

            facts: list[NewsroomFact] = []
            for item in fact_rows:
                source_id = source_by_announcement_id.get(item.announcement_id, "")
                facts.append(
                    NewsroomFact(
                        source_id=source_id,
                        source_url=source_urls.get(source_id, ""),
                        published_at=source_published.get(source_id, ""),
                        label=_clean(item.label),
                        metric=_clean(item.metric),
                        period=_clean(item.period),
                        value=_clean(item.value),
                        previous_value=_clean(item.previous_value),
                        comparator=_clean(item.comparator),
                        comparator_source_id=_clean(item.comparator_source_id),
                        basis=_clean(item.basis) or "reported",
                        unit=_clean(item.unit),
                        currency=_clean(item.currency),
                        information_status=_clean(item.information_status) or "new",
                    )
                )

            guidance: list[NewsroomGuidance] = []
            for item in guidance_rows:
                source_id = source_by_announcement_id.get(item.announcement_id, "")
                guidance.append(
                    NewsroomGuidance(
                        source_id=source_id,
                        source_url=source_urls.get(source_id, ""),
                        published_at=source_published.get(source_id, ""),
                        metric=_clean(item.metric),
                        period=_clean(item.period),
                        value=_clean(item.value),
                        status=_clean(item.status).lower(),
                        comparator=_clean(item.comparator),
                        previous_value=_clean(item.previous_value),
                        previous_source_id=_clean(item.previous_source_id),
                        note=_clean(item.note),
                    )
                )

            metric_history = self._metric_history(
                session,
                company_id=company_id,
                current_fact_rows=list(fact_rows),
                latest_at=latest_at,
            )
            open_claims = self._open_claims(
                session,
                company_id=company_id,
                latest_at=latest_at,
            )

            disclosure = dict(primary_run.disclosure_assessment or {})
            missing_items = [
                _clean(item)
                for item in list(disclosure.get("missing_items") or [])
                if _clean(item)
            ]
            challenges = [
                _clean(item) for item in list(primary_run.challenges_case or []) if _clean(item)
            ]
            watch_items = [
                _clean(item) for item in list(primary_run.watch_items or []) if _clean(item)
            ]

            # The copy desk's numerical support set is built from source evidence
            # and structured extracted facts only. It deliberately does not use
            # the Analyst headline/view/what_changed as self-validating evidence.
            evidence_texts: list[str] = [
                _clean(announcement.raw_text)
                for announcement, _company, _run in records
                if _clean(announcement.raw_text)
            ]
            for item in fact_rows:
                evidence_texts.extend(
                    [
                        _clean(item.value),
                        _clean(item.previous_value),
                        _clean(item.comparator),
                        _clean(item.note),
                    ]
                )
            for item in guidance_rows:
                evidence_texts.extend(
                    [
                        _clean(item.value),
                        _clean(item.previous_value),
                        _clean(item.comparator),
                        _clean(item.note),
                    ]
                )
            for history in metric_history:
                evidence_texts.extend(point.value for point in history.points)
            for claim, target_date, _claim_source_id, _claim_source_url in open_claims:
                evidence_texts.extend([claim, target_date])

        return NewsroomStoryPacket(
            story=story,
            facts=facts,
            guidance=guidance,
            metric_history=metric_history,
            challenges=challenges,
            watch_items=watch_items,
            missing_items=missing_items,
            management_language_mismatch=_clean(disclosure.get("management_language_mismatch")),
            open_claims=open_claims,
            evidence_texts=[item for item in evidence_texts if item],
            source_published_at=source_published,
            source_urls=source_urls,
        )

    def _metric_history(
        self,
        session: Session,
        *,
        company_id: object,
        current_fact_rows: list[FactRow],
        latest_at: datetime,
    ) -> list[NewsroomMetricHistory]:
        current_keys = {
            _series_key(item)
            for item in current_fact_rows
            if _clean(item.metric or item.label)
            and _clean(item.value)
            and _clean(item.basis) in {"reported", "calculated"}
        }
        if not current_keys:
            return []

        rows = session.execute(
            select(FactRow, AnnouncementRow)
            .join(AnnouncementRow, AnnouncementRow.id == FactRow.announcement_id)
            .join(AnalystRunRow, AnalystRunRow.id == FactRow.analyst_run_id)
            .where(
                FactRow.company_id == company_id,
                AnnouncementRow.published_at <= latest_at,
                AnalystRunRow.is_current.is_(True),
                AnalystRunRow.quality_status == "publishable",
                ~AnalystRunRow.model_version.like("deterministic-metadata%"),
            )
            .order_by(AnnouncementRow.published_at, FactRow.ordinal, FactRow.created_at)
        ).all()

        grouped: dict[
            tuple[str, str, str, str, str], list[tuple[FactRow, AnnouncementRow]]
        ] = defaultdict(list)
        for fact, announcement in rows:
            key = _series_key(fact)
            if key not in current_keys or not _clean(fact.value):
                continue
            grouped[key].append((fact, announcement))

        output: list[NewsroomMetricHistory] = []
        for _key, items in grouped.items():
            deduped: list[tuple[FactRow, AnnouncementRow]] = []
            seen: set[tuple[str, str]] = set()
            for fact, announcement in items:
                signature = (announcement.source_id, _clean(fact.value))
                if signature in seen:
                    continue
                seen.add(signature)
                deduped.append((fact, announcement))
            if len(deduped) < 2:
                continue
            recent = deduped[-4:]
            points = [
                NewsroomNumberPoint(
                    value=_clean(fact.value),
                    published_at=_iso(announcement.published_at),
                    source_id=announcement.source_id,
                    source_url=_clean(announcement.source_url),
                )
                for fact, announcement in recent
            ]
            numeric_values = [fact.value_numeric for fact, _announcement in recent]
            latest_fact = recent[-1][0]
            output.append(
                NewsroomMetricHistory(
                    metric=_clean(latest_fact.metric or latest_fact.label),
                    label=_clean(latest_fact.label or latest_fact.metric),
                    points=points,
                    direction=_direction(numeric_values),  # type: ignore[arg-type]
                )
            )
        return output

    @staticmethod
    def _open_claims(
        session: Session,
        *,
        company_id: object,
        latest_at: datetime,
    ) -> list[tuple[str, str, str, str]]:
        rows = session.execute(
            select(ManagementClaimRow, AnnouncementRow)
            .join(AnnouncementRow, AnnouncementRow.id == ManagementClaimRow.announcement_id)
            .join(AnalystRunRow, AnalystRunRow.id == ManagementClaimRow.analyst_run_id)
            .where(
                ManagementClaimRow.company_id == company_id,
                ManagementClaimRow.status == "open",
                AnnouncementRow.published_at <= latest_at,
                AnalystRunRow.is_current.is_(True),
                AnalystRunRow.quality_status == "publishable",
            )
            .order_by(AnnouncementRow.published_at.desc(), ManagementClaimRow.ordinal)
            .limit(5)
        ).all()
        return [
            (
                _clean(claim.claim),
                _clean(claim.target_date),
                announcement.source_id,
                _clean(announcement.source_url),
            )
            for claim, announcement in rows
            if _clean(claim.claim)
        ]
