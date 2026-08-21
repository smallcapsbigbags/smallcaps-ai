from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session, sessionmaker

from analyst.evidence import dedupe_source_urls
from database.db import session_scope
from database.models import AnalystRunRow, AnnouncementRow, CompanyRow, CorrectionRow, FactRow, GuidanceEventRow, ManagementClaimRow, PriceReactionRow

LONDON = ZoneInfo("Europe/London")


def _london_bounds(day: date) -> tuple[datetime, datetime]:
    start_local = datetime.combine(day, time.min, tzinfo=LONDON)
    end_local = datetime.combine(day + timedelta(days=1), time.min, tzinfo=LONDON)
    return start_local.astimezone(timezone.utc), end_local.astimezone(timezone.utc)


def _as_london(value: datetime) -> datetime:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(LONDON)


def _fact_dict(row: FactRow) -> dict[str, object]:
    return {"ordinal": row.ordinal, "label": row.label, "metric": row.metric, "period": row.period, "value": row.value, "unit": row.unit, "currency": row.currency, "as_of_date": row.as_of_date, "value_numeric": row.value_numeric, "value_low": row.value_low, "value_high": row.value_high, "basis": row.basis, "note": row.note, "comparator": row.comparator, "comparator_type": row.comparator_type, "comparator_source_id": row.comparator_source_id, "previous_value": row.previous_value, "information_status": row.information_status}


def _guidance_dict(row: GuidanceEventRow) -> dict[str, object]:
    return {"ordinal": row.ordinal, "metric": row.metric, "period": row.period, "value": row.value, "status": row.status, "comparator": row.comparator, "previous_value": row.previous_value, "previous_source_id": row.previous_source_id, "information_status": row.information_status, "note": row.note}


def _claim_dict(row: ManagementClaimRow) -> dict[str, object]:
    return {"ordinal": row.ordinal, "claim": row.claim, "claim_key": row.claim_key, "metric": row.metric, "target_value": row.target_value, "target_date": row.target_date, "status": row.status, "outcome": row.outcome, "evidence": row.evidence}


def _price_dict(row: PriceReactionRow | None) -> dict[str, object] | None:
    if row is None:
        return None
    return {"reaction_session": row.reaction_session, "phase": "close" if row.close_price is not None else "intraday", "previous_close": row.previous_close, "open_price": row.open_price, "latest_price": row.latest_price, "close_price": row.close_price, "daily_change_pct": row.event_day_return, "event_day_return": row.event_day_return, "return_1d": row.return_1d, "return_5d": row.return_5d, "return_20d": row.return_20d, "currency": row.currency, "source": row.source, "observed_at": row.observed_at.isoformat()}


class ProductRepository:
    """Read/write boundary for the public Feed, Analyst Note and price layer."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self.session_factory = session_factory

    @staticmethod
    def _latest_price_map(session: Session, announcement_ids: list[object]) -> dict[object, PriceReactionRow]:
        if not announcement_ids:
            return {}
        rows = session.scalars(select(PriceReactionRow).where(PriceReactionRow.announcement_id.in_(announcement_ids)).order_by(desc(PriceReactionRow.observed_at))).all()
        output: dict[object, PriceReactionRow] = {}
        for row in rows:
            output.setdefault(row.announcement_id, row)
        return output

    @staticmethod
    def _facts_by_run(session: Session, run_ids: list[object]) -> dict[object, list[FactRow]]:
        output: dict[object, list[FactRow]] = defaultdict(list)
        if not run_ids:
            return output
        rows = session.scalars(select(FactRow).where(FactRow.analyst_run_id.in_(run_ids)).order_by(FactRow.analyst_run_id, FactRow.ordinal, FactRow.created_at)).all()
        for row in rows:
            output[row.analyst_run_id].append(row)
        return output

    def list_feed(self, day: date, *, search: str = "", tickers: set[str] | None = None, sort: str = "impact", limit: int = 250) -> list[dict[str, Any]]:
        start, end = _london_bounds(day)
        with session_scope(self.session_factory) as session:
            rows = session.execute(select(AnnouncementRow, CompanyRow, AnalystRunRow).join(CompanyRow, CompanyRow.id == AnnouncementRow.company_id).join(AnalystRunRow, AnalystRunRow.announcement_id == AnnouncementRow.id).where(AnnouncementRow.published_at >= start, AnnouncementRow.published_at < end, AnalystRunRow.is_current.is_(True), AnalystRunRow.quality_status == "publishable")).all()
            query = search.strip().lower()
            ticker_filter = {item.upper() for item in tickers or set()}
            filtered: list[tuple[AnnouncementRow, CompanyRow, AnalystRunRow]] = []
            for announcement, company, run in rows:
                if ticker_filter and company.ticker.upper() not in ticker_filter:
                    continue
                haystack = " ".join((company.ticker, company.company_name, announcement.headline, announcement.announcement_type, run.headline, run.takeaway)).lower()
                if query and query not in haystack:
                    continue
                filtered.append((announcement, company, run))
            if sort == "latest":
                filtered.sort(key=lambda item: (item[0].published_at, item[2].impact_score), reverse=True)
            else:
                filtered.sort(key=lambda item: (item[2].impact_score, item[0].published_at), reverse=True)
            filtered = filtered[:limit]
            run_ids = [run.id for _announcement, _company, run in filtered]
            announcement_ids = [announcement.id for announcement, _company, _run in filtered]
            facts_by_run = self._facts_by_run(session, run_ids)
            prices = self._latest_price_map(session, announcement_ids)
            output: list[dict[str, Any]] = []
            for announcement, company, run in filtered:
                facts = [_fact_dict(row) for row in facts_by_run.get(run.id, []) if row.basis not in {"not-disclosed", "source-warning"}][:3]
                source_urls = dedupe_source_urls(announcement.source_urls, announcement.source_url, run.source_references)
                output.append({"source_id": announcement.source_id, "ticker": company.ticker, "company": company.company_name, "published_at": _as_london(announcement.published_at).isoformat(), "rns_type": announcement.announcement_type, "impact_colour": run.impact_colour, "impact_score": run.impact_score, "impact_level": run.impact_level, "impact_rationale": run.impact_rationale, "headline": run.headline, "takeaway": run.takeaway, "key_facts": facts, "source_url": source_urls[0] if source_urls else "", "price": _price_dict(prices.get(announcement.id))})
            return output

    def get_note(self, source_id: str, *, public_only: bool = True) -> dict[str, Any] | None:
        with session_scope(self.session_factory) as session:
            conditions = [AnnouncementRow.source_id == source_id, AnalystRunRow.is_current.is_(True)]
            if public_only:
                conditions.append(AnalystRunRow.quality_status == "publishable")
            row = session.execute(select(AnnouncementRow, CompanyRow, AnalystRunRow).join(CompanyRow, CompanyRow.id == AnnouncementRow.company_id).join(AnalystRunRow, AnalystRunRow.announcement_id == AnnouncementRow.id).where(*conditions)).first()
            if row is None:
                return None
            announcement, company, run = row
            facts = session.scalars(select(FactRow).where(FactRow.analyst_run_id == run.id).order_by(FactRow.ordinal, FactRow.created_at)).all()
            guidance = session.scalars(select(GuidanceEventRow).where(GuidanceEventRow.analyst_run_id == run.id).order_by(GuidanceEventRow.ordinal, GuidanceEventRow.created_at)).all()
            claims = session.scalars(select(ManagementClaimRow).where(ManagementClaimRow.analyst_run_id == run.id).order_by(ManagementClaimRow.ordinal, ManagementClaimRow.created_at)).all()
            price = self._latest_price_map(session, [announcement.id]).get(announcement.id)
            source_urls = dedupe_source_urls(announcement.source_urls, announcement.source_url, run.source_references)
            return {"source_id": announcement.source_id, "ticker": company.ticker, "company": company.company_name, "published_at": _as_london(announcement.published_at).isoformat(), "rns_type": announcement.announcement_type, "impact_colour": run.impact_colour, "impact_score": run.impact_score, "impact_level": run.impact_level, "impact_rationale": run.impact_rationale, "impact_drivers": list(run.impact_drivers), "headline": run.headline, "takeaway": run.takeaway, "key_facts": [_fact_dict(item) for item in facts], "new_information": list(run.new_information), "reiterated_information": list(run.reiterated_information), "what_changed": dict(run.what_changed), "analyst_view": run.analyst_view, "supports_case": list(run.supports_case), "challenges_case": list(run.challenges_case), "guidance_events": [_guidance_dict(item) for item in guidance], "management_claims": [_claim_dict(item) for item in claims], "watch_items": list(run.watch_items), "disclosure_assessment": dict(run.disclosure_assessment), "source_urls": source_urls, "source_note": announcement.source_note, "source_warnings": list(run.source_warnings), "evidence_status": announcement.evidence_status, "quality_status": run.quality_status, "quality_flags": list(run.quality_flags), "confidence": run.confidence, "price": _price_dict(price)}

    def company_history(self, ticker: str, *, limit: int = 200) -> dict[str, Any] | None:
        clean_ticker = ticker.upper().strip().replace(".L", "")
        with session_scope(self.session_factory) as session:
            company = session.scalar(select(CompanyRow).where(CompanyRow.ticker == clean_ticker))
            if company is None:
                return None
            public_conditions = (AnnouncementRow.company_id == company.id, AnalystRunRow.is_current.is_(True), AnalystRunRow.quality_status == "publishable")
            total_count, first_published = session.execute(select(func.count(AnnouncementRow.id), func.min(AnnouncementRow.published_at)).join(AnalystRunRow, AnalystRunRow.announcement_id == AnnouncementRow.id).where(*public_conditions)).one()
            rows = session.execute(select(AnnouncementRow, AnalystRunRow).join(AnalystRunRow, AnalystRunRow.announcement_id == AnnouncementRow.id).where(*public_conditions).order_by(desc(AnnouncementRow.published_at)).limit(limit)).all()
            prices = self._latest_price_map(session, [announcement.id for announcement, _run in rows])
            announcements = []
            for announcement, run in rows:
                source_urls = dedupe_source_urls(announcement.source_urls, announcement.source_url, run.source_references)
                announcements.append({"source_id": announcement.source_id, "published_at": _as_london(announcement.published_at).isoformat(), "rns_type": announcement.announcement_type, "impact_colour": run.impact_colour, "impact_score": run.impact_score, "impact_level": run.impact_level, "headline": run.headline, "takeaway": run.takeaway, "source_url": source_urls[0] if source_urls else "", "price": _price_dict(prices.get(announcement.id))})
            coverage_since = _as_london(first_published).isoformat() if first_published is not None else ""
            return {"ticker": company.ticker, "company": company.company_name, "isin": company.isin, "market": company.market, "coverage_since": coverage_since, "announcement_count": int(total_count or 0), "displayed_count": len(announcements), "has_more": int(total_count or 0) > len(announcements), "announcements": announcements}

    def list_review_queue(self, *, limit: int = 50) -> list[dict[str, Any]]:
        with session_scope(self.session_factory) as session:
            rows = session.execute(select(AnnouncementRow, CompanyRow, AnalystRunRow).join(CompanyRow, CompanyRow.id == AnnouncementRow.company_id).join(AnalystRunRow, AnalystRunRow.announcement_id == AnnouncementRow.id).where(AnalystRunRow.is_current.is_(True), AnalystRunRow.quality_status == "review").order_by(desc(AnnouncementRow.published_at)).limit(limit)).all()
            return [{"source_id": announcement.source_id, "ticker": company.ticker, "company": company.company_name, "published_at": _as_london(announcement.published_at).isoformat(), "headline": run.headline, "quality_flags": list(run.quality_flags)} for announcement, company, run in rows]

    def approve_review(self, source_id: str, *, reason: str, corrected_by: str = "owner") -> dict[str, Any]:
        clean_reason = reason.strip()
        if len(clean_reason) < 12:
            raise ValueError("Approval reason must explain the source check or correction")
        with session_scope(self.session_factory) as session:
            row = session.execute(select(AnnouncementRow, AnalystRunRow).join(AnalystRunRow, AnalystRunRow.announcement_id == AnnouncementRow.id).where(AnnouncementRow.source_id == source_id, AnalystRunRow.is_current.is_(True))).first()
            if row is None:
                raise LookupError(f"Unknown source_id: {source_id}")
            announcement, run = row
            if run.quality_status != "review":
                raise ValueError("Only review-required current runs can be approved")
            original = {"quality_status": run.quality_status, "quality_flags": list(run.quality_flags)}
            approval_flag = {"code": "OWNER_APPROVED", "severity": "info", "message": f"Owner approved after source review: {clean_reason}"}
            run.quality_status = "publishable"
            run.quality_flags = [*list(run.quality_flags), approval_flag]
            session.add(CorrectionRow(analyst_run_id=run.id, field_path="quality_status", original_value=original, corrected_value={"quality_status": "publishable", "approval_flag": approval_flag}, reason=clean_reason, corrected_by=corrected_by))
            session.flush()
            return {"source_id": announcement.source_id, "quality_status": run.quality_status, "quality_flags": list(run.quality_flags)}

    def list_price_targets(self, *, published_after: datetime, published_before: datetime) -> list[dict[str, Any]]:
        with session_scope(self.session_factory) as session:
            rows = session.execute(select(AnnouncementRow, CompanyRow).join(CompanyRow, CompanyRow.id == AnnouncementRow.company_id).join(AnalystRunRow, AnalystRunRow.announcement_id == AnnouncementRow.id).where(AnnouncementRow.published_at >= published_after, AnnouncementRow.published_at < published_before, AnalystRunRow.is_current.is_(True), AnalystRunRow.quality_status == "publishable").order_by(AnnouncementRow.published_at)).all()
            prices = self._latest_price_map(session, [announcement.id for announcement, _company in rows])
            return [{"source_id": announcement.source_id, "ticker": company.ticker, "published_at": _as_london(announcement.published_at), "has_frozen_close": bool(prices.get(announcement.id) and prices[announcement.id].close_price is not None)} for announcement, company in rows]

    def upsert_price_reaction(self, *, source_id: str, reaction_session: str, phase: str, previous_close: float, latest_price: float, daily_change_pct: float, currency: str, source: str, observed_at: datetime) -> dict[str, Any]:
        with session_scope(self.session_factory) as session:
            announcement = session.scalar(select(AnnouncementRow).where(AnnouncementRow.source_id == source_id))
            if announcement is None:
                raise LookupError(f"Unknown source_id: {source_id}")
            row = session.scalar(select(PriceReactionRow).where(PriceReactionRow.announcement_id == announcement.id, PriceReactionRow.reaction_session == reaction_session))
            if row is None:
                row = PriceReactionRow(announcement_id=announcement.id, reaction_session=reaction_session)
                session.add(row)
            row.previous_close = previous_close
            row.latest_price = latest_price
            row.event_day_return = daily_change_pct
            row.currency = currency
            row.source = source
            row.observed_at = observed_at
            if phase == "close":
                row.close_price = latest_price
            session.flush()
            return _price_dict(row) or {}
