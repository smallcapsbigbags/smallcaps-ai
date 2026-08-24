from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from typing import Any
from urllib.parse import quote
from zoneinfo import ZoneInfo

from sqlalchemy import desc, func, or_, select
from sqlalchemy.orm import Session, sessionmaker

from analyst.evidence import dedupe_source_urls
from analyst.models import KeyFact
from analyst.monitoring_sheet import (
    MonitoringOutlook,
    MonitoringSignal,
    balance_sheet_fact_sort_key,
    is_balance_sheet_fact,
    monitoring_outlook_from_statuses,
    monitoring_signal_from_colour,
)
from database.db import session_scope
from database.models import (
    AnalystRunRow,
    AnnouncementRow,
    CompanyRow,
    FactRow,
    GuidanceEventRow,
    ManagementClaimRow,
    PriceReactionRow,
)
from product.monitoring import (
    MonitoringImpact,
    MonitoringProvenance,
    MonitoringQueryEcho,
    MonitoringResearch,
    MonitoringSheetDetail,
    MonitoringSheetPage,
    MonitoringSheetRow,
    MonitoringSort,
    MonitoringWhatChanged,
    balance_sheet_from_fact,
    compact_ai_view,
    market_reaction_from_price,
    monitoring_claim,
    monitoring_disclosure,
    monitoring_fact,
    monitoring_guidance,
)

LONDON = ZoneInfo("Europe/London")
_MAX_RANGE_DAYS = 366
_BALANCE_SHEET_TERMS = (
    "net debt",
    "net cash",
    "cash balance",
    "cash",
    "gross debt",
    "liquidity",
    "working capital",
    "funding runway",
    "cash runway",
    "covenant headroom",
)
_VALID_SIGNALS = {"GREEN", "AMBER", "RED", "NO COLOUR"}
_VALID_OUTLOOKS = {
    "UPGRADED",
    "MAINTAINED",
    "DOWNGRADED",
    "NEW GUIDANCE",
    "MIXED",
    "N/A",
}


@dataclass(frozen=True)
class MonitoringSheetQuery:
    date_from: date
    date_to: date
    tickers: tuple[str, ...] = ()
    search: str = ""
    signals: tuple[MonitoringSignal, ...] = ()
    outlooks: tuple[MonitoringOutlook, ...] = ()
    sort: MonitoringSort = "latest"
    limit: int = 100
    offset: int = 0

    def __post_init__(self) -> None:
        if self.date_to < self.date_from:
            raise ValueError("date_to cannot be earlier than date_from")
        if (self.date_to - self.date_from).days > _MAX_RANGE_DAYS:
            raise ValueError(f"date range cannot exceed {_MAX_RANGE_DAYS} days")
        if not 1 <= self.limit <= 250:
            raise ValueError("limit must be between 1 and 250")
        if self.offset < 0:
            raise ValueError("offset cannot be negative")
        if self.sort not in {"latest", "impact"}:
            raise ValueError("sort must be 'latest' or 'impact'")

        tickers = tuple(
            dict.fromkeys(
                _normalise_ticker(item)
                for item in self.tickers
                if _normalise_ticker(item)
            )
        )
        signals = tuple(
            dict.fromkeys(str(item).strip().upper() for item in self.signals)
        )
        outlooks = tuple(
            dict.fromkeys(str(item).strip().upper() for item in self.outlooks)
        )
        invalid_signals = set(signals) - _VALID_SIGNALS
        invalid_outlooks = set(outlooks) - _VALID_OUTLOOKS
        if invalid_signals:
            raise ValueError(
                f"unsupported signal: {', '.join(sorted(invalid_signals))}"
            )
        if invalid_outlooks:
            raise ValueError(
                f"unsupported outlook: {', '.join(sorted(invalid_outlooks))}"
            )

        object.__setattr__(self, "tickers", tickers)
        object.__setattr__(self, "signals", signals)
        object.__setattr__(self, "outlooks", outlooks)
        object.__setattr__(self, "search", " ".join(self.search.strip().split()))


class MonitoringSheetRepository:
    """Database-backed public read model for the SmallcapsBigBags monitoring sheet."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self.session_factory = session_factory

    def list_rows(self, query: MonitoringSheetQuery) -> MonitoringSheetPage:
        start, end = _london_bounds(query.date_from, query.date_to)
        with session_scope(self.session_factory) as session:
            statement = (
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
                )
            )
            if query.tickers:
                statement = statement.where(CompanyRow.ticker.in_(query.tickers))
            if query.search:
                pattern = f"%{_escape_like(query.search.lower())}%"
                statement = statement.where(
                    or_(
                        func.lower(CompanyRow.ticker).like(pattern, escape="\\"),
                        func.lower(CompanyRow.company_name).like(
                            pattern, escape="\\"
                        ),
                        func.lower(AnnouncementRow.headline).like(
                            pattern, escape="\\"
                        ),
                        func.lower(AnnouncementRow.announcement_type).like(
                            pattern, escape="\\"
                        ),
                        func.lower(AnalystRunRow.headline).like(
                            pattern, escape="\\"
                        ),
                        func.lower(AnalystRunRow.takeaway).like(
                            pattern, escape="\\"
                        ),
                    )
                )

            records = session.execute(statement).all()
            rows = self._build_rows(session, records)

        if query.signals:
            allowed_signals = set(query.signals)
            rows = [row for row in rows if row.signal in allowed_signals]
        if query.outlooks:
            allowed_outlooks = set(query.outlooks)
            rows = [row for row in rows if row.outlook in allowed_outlooks]

        if query.sort == "impact":
            rows.sort(
                key=lambda row: (row.impact.score, row.published_at, row.source_id),
                reverse=True,
            )
        else:
            rows.sort(
                key=lambda row: (row.published_at, row.impact.score, row.source_id),
                reverse=True,
            )

        total = len(rows)
        items = rows[query.offset : query.offset + query.limit]
        return MonitoringSheetPage(
            generated_at=datetime.now(timezone.utc),
            query=MonitoringQueryEcho(
                date_from=query.date_from.isoformat(),
                date_to=query.date_to.isoformat(),
                tickers=list(query.tickers),
                search=query.search,
                signals=list(query.signals),
                outlooks=list(query.outlooks),
                sort=query.sort,
                limit=query.limit,
                offset=query.offset,
            ),
            total=total,
            count=len(items),
            has_more=query.offset + len(items) < total,
            items=items,
        )

    def get_detail(
        self,
        source_id: str,
        *,
        public_only: bool = True,
    ) -> MonitoringSheetDetail | None:
        clean_source_id = source_id.strip()
        if not clean_source_id:
            return None

        with session_scope(self.session_factory) as session:
            conditions = [
                AnnouncementRow.source_id == clean_source_id,
                AnalystRunRow.is_current.is_(True),
            ]
            if public_only:
                conditions.append(AnalystRunRow.quality_status == "publishable")
            record = session.execute(
                select(AnnouncementRow, CompanyRow, AnalystRunRow)
                .join(CompanyRow, CompanyRow.id == AnnouncementRow.company_id)
                .join(
                    AnalystRunRow,
                    AnalystRunRow.announcement_id == AnnouncementRow.id,
                )
                .where(*conditions)
            ).first()
            if record is None:
                return None

            announcement, company, run = record
            facts = session.scalars(
                select(FactRow)
                .where(FactRow.analyst_run_id == run.id)
                .order_by(FactRow.ordinal, FactRow.created_at)
            ).all()
            guidance = session.scalars(
                select(GuidanceEventRow)
                .where(GuidanceEventRow.analyst_run_id == run.id)
                .order_by(GuidanceEventRow.ordinal, GuidanceEventRow.created_at)
            ).all()
            claims = session.scalars(
                select(ManagementClaimRow)
                .where(ManagementClaimRow.analyst_run_id == run.id)
                .order_by(ManagementClaimRow.ordinal, ManagementClaimRow.created_at)
            ).all()
            price = self._latest_price_map(session, [announcement.id]).get(
                announcement.id
            )
            carried_candidates = self._carried_balance_candidates(
                session,
                company_ids=[company.id],
                published_before=announcement.published_at,
            )
            balance = self._select_balance_sheet(
                announcement=announcement,
                current_facts=list(facts),
                carried_candidates=carried_candidates.get(company.id, []),
            )
            row = self._build_row(
                announcement=announcement,
                company=company,
                run=run,
                facts=list(facts),
                guidance=list(guidance),
                price=price,
                balance=balance,
            )
            what_changed = _what_changed(run.what_changed)
            source_urls = dedupe_source_urls(
                announcement.source_urls,
                announcement.source_url,
                run.source_references,
            )
            compacted_view, compacted = compact_ai_view(run.analyst_view)
            if compacted_view != row.ai_view:
                raise RuntimeError("monitoring AI View adapter is inconsistent")

            research = MonitoringResearch(
                verdict=run.headline,
                takeaway=run.takeaway,
                what_changed=what_changed,
                evidence=[monitoring_fact(_fact_dict(item)) for item in facts],
                analyst_view=run.analyst_view,
                supports_case=list(run.supports_case),
                challenges_case=list(run.challenges_case),
                guidance_events=[
                    monitoring_guidance(_guidance_dict(item)) for item in guidance
                ],
                management_claims=[
                    monitoring_claim(_claim_dict(item)) for item in claims
                ],
                watch_items=list(run.watch_items),
                disclosure=monitoring_disclosure(run.disclosure_assessment),
                provenance=MonitoringProvenance(
                    evidence_status=announcement.evidence_status,
                    quality_status=run.quality_status,
                    confidence=run.confidence,
                    analysis_version=run.analysis_version,
                    prompt_version=run.prompt_version,
                    model_version=run.model_version,
                    source_note=announcement.source_note,
                    source_warnings=list(run.source_warnings),
                    source_urls=source_urls,
                    ai_view_compacted=compacted,
                ),
            )
            return MonitoringSheetDetail(**row.model_dump(), research=research)

    def health(self) -> dict[str, object]:
        with session_scope(self.session_factory) as session:
            dialect = (
                session.bind.dialect.name
                if session.bind is not None
                else "unknown"
            )
            publishable = session.scalar(
                select(func.count())
                .select_from(AnalystRunRow)
                .where(
                    AnalystRunRow.is_current.is_(True),
                    AnalystRunRow.quality_status == "publishable",
                )
            )
            session.scalar(select(1))
            return {
                "status": "ok",
                "schema_version": "scbb-monitoring-v1",
                "database": dialect,
                "publishable_records": int(publishable or 0),
            }

    def _build_rows(
        self,
        session: Session,
        records: list[tuple[AnnouncementRow, CompanyRow, AnalystRunRow]],
    ) -> list[MonitoringSheetRow]:
        if not records:
            return []

        run_ids = [run.id for _announcement, _company, run in records]
        announcement_ids = [
            announcement.id for announcement, _company, _run in records
        ]
        company_ids = list(
            dict.fromkeys(company.id for _announcement, company, _run in records)
        )
        facts_by_run = self._facts_by_run(session, run_ids)
        guidance_by_run = self._guidance_by_run(session, run_ids)
        prices = self._latest_price_map(session, announcement_ids)
        latest_published = max(
            announcement.published_at for announcement, _company, _run in records
        )
        carried = self._carried_balance_candidates(
            session,
            company_ids=company_ids,
            published_before=latest_published,
        )

        output: list[MonitoringSheetRow] = []
        for announcement, company, run in records:
            current_facts = facts_by_run.get(run.id, [])
            balance = self._select_balance_sheet(
                announcement=announcement,
                current_facts=current_facts,
                carried_candidates=carried.get(company.id, []),
            )
            output.append(
                self._build_row(
                    announcement=announcement,
                    company=company,
                    run=run,
                    facts=current_facts,
                    guidance=guidance_by_run.get(run.id, []),
                    price=prices.get(announcement.id),
                    balance=balance,
                )
            )
        return output

    def _build_row(
        self,
        *,
        announcement: AnnouncementRow,
        company: CompanyRow,
        run: AnalystRunRow,
        facts: list[FactRow],
        guidance: list[GuidanceEventRow],
        price: PriceReactionRow | None,
        balance: tuple[FactRow | None, str, AnnouncementRow | None],
    ) -> MonitoringSheetRow:
        del facts
        fact, balance_status, balance_announcement = balance
        source_urls = dedupe_source_urls(
            announcement.source_urls,
            announcement.source_url,
            run.source_references,
        )
        what_changed = _what_changed(run.what_changed)
        ai_view, _compacted = compact_ai_view(run.analyst_view)
        price_payload = _price_dict(price)
        balance_payload = _fact_dict(fact) if fact is not None else None
        balance_source_id = (
            balance_announcement.source_id
            if balance_announcement is not None
            else ""
        )
        balance_source_published_at = (
            _as_london(balance_announcement.published_at).isoformat()
            if balance_announcement is not None
            else ""
        )
        return MonitoringSheetRow(
            source_id=announcement.source_id,
            ticker=company.ticker,
            company=company.company_name,
            market=company.market,
            isin=company.isin,
            published_at=_as_london(announcement.published_at),
            rns_title=announcement.headline,
            rns_type=announcement.announcement_type,
            signal=monitoring_signal_from_colour(run.impact_colour),
            what_changed=what_changed.today,
            ai_view=ai_view,
            outlook=monitoring_outlook_from_statuses(
                item.status for item in guidance
            ),
            market_reaction=market_reaction_from_price(price_payload),
            balance_sheet=balance_sheet_from_fact(
                balance_payload,
                status=balance_status,  # type: ignore[arg-type]
                source_id=balance_source_id,
                source_published_at=balance_source_published_at,
            ),
            impact=MonitoringImpact(
                score=run.impact_score,
                level=run.impact_level,
            ),
            detail_url=(
                f"/api/v1/monitoring/{quote(announcement.source_id, safe='')}"
            ),
            original_source_url=source_urls[0] if source_urls else "",
        )

    @staticmethod
    def _facts_by_run(
        session: Session,
        run_ids: list[object],
    ) -> dict[object, list[FactRow]]:
        output: dict[object, list[FactRow]] = defaultdict(list)
        if not run_ids:
            return output
        rows = session.scalars(
            select(FactRow)
            .where(FactRow.analyst_run_id.in_(run_ids))
            .order_by(
                FactRow.analyst_run_id,
                FactRow.ordinal,
                FactRow.created_at,
            )
        ).all()
        for row in rows:
            output[row.analyst_run_id].append(row)
        return output

    @staticmethod
    def _guidance_by_run(
        session: Session,
        run_ids: list[object],
    ) -> dict[object, list[GuidanceEventRow]]:
        output: dict[object, list[GuidanceEventRow]] = defaultdict(list)
        if not run_ids:
            return output
        rows = session.scalars(
            select(GuidanceEventRow)
            .where(GuidanceEventRow.analyst_run_id.in_(run_ids))
            .order_by(
                GuidanceEventRow.analyst_run_id,
                GuidanceEventRow.ordinal,
                GuidanceEventRow.created_at,
            )
        ).all()
        for row in rows:
            output[row.analyst_run_id].append(row)
        return output

    @staticmethod
    def _latest_price_map(
        session: Session,
        announcement_ids: list[object],
    ) -> dict[object, PriceReactionRow]:
        if not announcement_ids:
            return {}
        rows = session.scalars(
            select(PriceReactionRow)
            .where(PriceReactionRow.announcement_id.in_(announcement_ids))
            .order_by(desc(PriceReactionRow.observed_at))
        ).all()
        output: dict[object, PriceReactionRow] = {}
        for row in rows:
            output.setdefault(row.announcement_id, row)
        return output

    @staticmethod
    def _carried_balance_candidates(
        session: Session,
        *,
        company_ids: list[object],
        published_before: datetime,
    ) -> dict[object, list[tuple[FactRow, AnnouncementRow]]]:
        output: dict[object, list[tuple[FactRow, AnnouncementRow]]] = defaultdict(
            list
        )
        if not company_ids:
            return output

        predicates = []
        for term in _BALANCE_SHEET_TERMS:
            pattern = f"%{term}%"
            predicates.extend(
                (
                    func.lower(FactRow.metric).like(pattern),
                    func.lower(FactRow.label).like(pattern),
                )
            )

        rows = session.execute(
            select(FactRow, AnnouncementRow)
            .join(
                AnnouncementRow,
                AnnouncementRow.id == FactRow.announcement_id,
            )
            .join(AnalystRunRow, AnalystRunRow.id == FactRow.analyst_run_id)
            .where(
                FactRow.company_id.in_(company_ids),
                AnnouncementRow.published_at < published_before,
                AnalystRunRow.is_current.is_(True),
                AnalystRunRow.quality_status == "publishable",
                FactRow.basis.in_(("reported", "calculated")),
                or_(*predicates),
            )
            .order_by(
                FactRow.company_id,
                desc(AnnouncementRow.published_at),
                FactRow.ordinal,
            )
        ).all()
        for fact, announcement in rows:
            output[fact.company_id].append((fact, announcement))
        return output

    @staticmethod
    def _select_balance_sheet(
        *,
        announcement: AnnouncementRow,
        current_facts: list[FactRow],
        carried_candidates: list[tuple[FactRow, AnnouncementRow]],
    ) -> tuple[FactRow | None, str, AnnouncementRow | None]:
        current = [
            (row, _key_fact(row))
            for row in current_facts
            if row.basis not in {"not-disclosed", "source-warning"}
        ]
        current = [item for item in current if is_balance_sheet_fact(item[1])]
        if current:
            row, _fact = min(
                current,
                key=lambda item: balance_sheet_fact_sort_key(item[1]),
            )
            return row, "current", announcement

        eligible = [
            (fact, source)
            for fact, source in carried_candidates
            if source.published_at < announcement.published_at
        ]
        if not eligible:
            return None, "not-disclosed", None

        latest = max(source.published_at for _fact, source in eligible)
        same_disclosure = [
            (fact, source)
            for fact, source in eligible
            if source.published_at == latest
        ]
        fact, source = min(
            same_disclosure,
            key=lambda item: balance_sheet_fact_sort_key(_key_fact(item[0])),
        )
        return fact, "carried", source


def _key_fact(row: FactRow) -> KeyFact:
    return KeyFact(
        label=row.label,
        value=row.value,
        basis=row.basis,
        note=row.note,
        metric=row.metric,
        period=row.period,
        unit=row.unit,
        currency=row.currency,
        as_of_date=row.as_of_date,
        value_numeric=row.value_numeric,
        value_low=row.value_low,
        value_high=row.value_high,
        comparator=row.comparator,
        comparator_type=row.comparator_type,
        comparator_source_id=row.comparator_source_id,
        previous_value=row.previous_value,
        information_status=row.information_status,
    )


def _fact_dict(row: FactRow | None) -> dict[str, Any]:
    if row is None:
        return {}
    return {
        "ordinal": row.ordinal,
        "label": row.label,
        "metric": row.metric,
        "period": row.period,
        "value": row.value,
        "unit": row.unit,
        "currency": row.currency,
        "as_of_date": row.as_of_date,
        "value_numeric": row.value_numeric,
        "value_low": row.value_low,
        "value_high": row.value_high,
        "basis": row.basis,
        "note": row.note,
        "comparator": row.comparator,
        "comparator_type": row.comparator_type,
        "comparator_source_id": row.comparator_source_id,
        "previous_value": row.previous_value,
        "information_status": row.information_status,
    }


def _guidance_dict(row: GuidanceEventRow) -> dict[str, Any]:
    return {
        "ordinal": row.ordinal,
        "metric": row.metric,
        "period": row.period,
        "value": row.value,
        "status": row.status,
        "comparator": row.comparator,
        "previous_value": row.previous_value,
        "previous_source_id": row.previous_source_id,
        "information_status": row.information_status,
        "note": row.note,
    }


def _claim_dict(row: ManagementClaimRow) -> dict[str, Any]:
    return {
        "ordinal": row.ordinal,
        "claim": row.claim,
        "claim_key": row.claim_key,
        "metric": row.metric,
        "target_value": row.target_value,
        "target_date": row.target_date,
        "status": row.status,
        "outcome": row.outcome,
        "evidence": row.evidence,
    }


def _price_dict(row: PriceReactionRow | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return {
        "reaction_session": row.reaction_session,
        "phase": "close" if row.close_price is not None else "intraday",
        "previous_close": row.previous_close,
        "open_price": row.open_price,
        "latest_price": row.latest_price,
        "close_price": row.close_price,
        "daily_change_pct": row.event_day_return,
        "event_day_return": row.event_day_return,
        "return_1d": row.return_1d,
        "return_5d": row.return_5d,
        "return_20d": row.return_20d,
        "currency": row.currency,
        "source": row.source,
        "observed_at": row.observed_at.isoformat(),
    }


def _what_changed(value: dict[str, Any] | None) -> MonitoringWhatChanged:
    payload = dict(value or {})
    status = str(payload.get("coverage_status") or "building")
    if status not in {"building", "established"}:
        status = "building"
    return MonitoringWhatChanged(
        before=str(payload.get("before") or "").strip(),
        today=str(payload.get("today") or "").strip(),
        read_through=str(payload.get("read_through") or "").strip(),
        coverage_status=status,  # type: ignore[arg-type]
    )


def _london_bounds(start_day: date, end_day: date) -> tuple[datetime, datetime]:
    start_local = datetime.combine(start_day, time.min, tzinfo=LONDON)
    end_local = datetime.combine(
        end_day + timedelta(days=1),
        time.min,
        tzinfo=LONDON,
    )
    return start_local.astimezone(timezone.utc), end_local.astimezone(timezone.utc)


def _as_london(value: datetime) -> datetime:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(LONDON)


def _normalise_ticker(value: str) -> str:
    return value.upper().strip().replace(".L", "").rstrip(".-")


def _escape_like(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace("%", "\\%")
        .replace("_", "\\_")
    )
