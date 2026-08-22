from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from database.db import session_scope
from database.models import AnalystRunRow, AnnouncementRow, CompanyRow
from database.repository import IntelligenceRepository


def _clean_ticker(value: str) -> str:
    return value.upper().strip().replace(".L", "").rstrip(".-")


class CompanyValidationRepository:
    """Read boundary used by the zero-token Phase 3 live validation job."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self.session_factory = session_factory
        self.intelligence = IntelligenceRepository(session_factory)

    def list_candidates(
        self,
        *,
        min_announcements: int = 2,
        limit: int = 10,
        preferred_tickers: tuple[str, ...] = ("SPR",),
    ) -> list[dict[str, Any]]:
        """Rank covered companies by chronology depth and event-type diversity."""

        minimum = max(1, min_announcements)
        preferred = {_clean_ticker(item) for item in preferred_tickers}
        with session_scope(self.session_factory) as session:
            rows = session.execute(
                select(CompanyRow, AnnouncementRow, AnalystRunRow)
                .join(
                    AnnouncementRow,
                    AnnouncementRow.company_id == CompanyRow.id,
                )
                .join(
                    AnalystRunRow,
                    AnalystRunRow.announcement_id == AnnouncementRow.id,
                )
                .where(
                    AnalystRunRow.is_current.is_(True),
                    AnalystRunRow.quality_status == "publishable",
                )
                .order_by(CompanyRow.ticker, AnnouncementRow.published_at)
            ).all()

        grouped: dict[str, list[tuple[CompanyRow, AnnouncementRow, AnalystRunRow]]] = (
            defaultdict(list)
        )
        for company, announcement, run in rows:
            grouped[company.ticker].append((company, announcement, run))

        output: list[dict[str, Any]] = []
        for ticker, items in grouped.items():
            if len(items) < minimum:
                continue
            company = items[0][0]
            dates = [announcement.published_at for _company, announcement, _run in items]
            event_types = sorted(
                {
                    announcement.announcement_type
                    for _company, announcement, _run in items
                    if announcement.announcement_type
                }
            )
            versions = sorted(
                {
                    run.analysis_version
                    for _company, _announcement, run in items
                    if run.analysis_version
                }
            )
            coverage_days = (
                max(0, (dates[-1].date() - dates[0].date()).days)
                if len(dates) > 1
                else 0
            )
            output.append(
                {
                    "ticker": ticker,
                    "company": company.company_name,
                    "announcement_count": len(items),
                    "event_types": event_types,
                    "event_type_count": len(event_types),
                    "coverage_since": dates[0].isoformat(),
                    "latest_published_at": dates[-1].isoformat(),
                    "coverage_days": coverage_days,
                    "analysis_versions": versions,
                    "preferred": ticker in preferred,
                }
            )

        output.sort(
            key=lambda item: (
                bool(item["preferred"]),
                int(item["announcement_count"]),
                int(item["event_type_count"]),
                int(item["coverage_days"]),
                str(item["latest_published_at"]),
            ),
            reverse=True,
        )
        return output[: max(0, limit)]

    def load_timeline(
        self,
        ticker: str,
        *,
        limit: int = 240,
    ) -> dict[str, Any] | None:
        """Load one company's complete publishable chronology for reconstruction."""

        clean_ticker = _clean_ticker(ticker)
        with session_scope(self.session_factory) as session:
            company = session.scalar(
                select(CompanyRow).where(CompanyRow.ticker == clean_ticker)
            )
            if company is None:
                return None
            company_name = company.company_name

        records = self.intelligence.load_prior_context(
            clean_ticker,
            before=datetime.now(timezone.utc) + timedelta(days=1),
            limit=max(1, limit),
        )
        enriched: list[dict[str, object]] = []
        for record in records:
            enriched.append(
                {
                    **record,
                    "ticker": clean_ticker,
                    "company": company_name,
                }
            )
        return {
            "ticker": clean_ticker,
            "company": company_name,
            "records": enriched,
            "announcement_count": len(enriched),
        }
