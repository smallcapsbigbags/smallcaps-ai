from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import Select, desc, select, update
from sqlalchemy.orm import Session, sessionmaker

from analyst.models import AnalystNote, AnnouncementInput, PersistedAnalysis
from analyst.version import ANALYSIS_VERSION
from database.db import session_scope
from database.models import (
    AnalystRunRow,
    AnnouncementRow,
    CompanyRow,
    FactRow,
    GuidanceEventRow,
    ManagementClaimRow,
)


class IntelligenceRepository:
    """Versioned persistence boundary for the AIM intelligence moat."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self.session_factory = session_factory

    def _company_by_ticker(self, ticker: str) -> Select[tuple[CompanyRow]]:
        return select(CompanyRow).where(CompanyRow.ticker == ticker.upper())

    def save_analysis(
        self,
        announcement: AnnouncementInput,
        note: AnalystNote,
        *,
        prompt_version: str,
        model_version: str,
    ) -> PersistedAnalysis:
        if note.source_id != announcement.source_id:
            raise ValueError("AnalystNote source_id must match the announcement source_id")

        with session_scope(self.session_factory) as session:
            company = session.scalar(self._company_by_ticker(announcement.ticker))
            if company is None:
                company = CompanyRow(
                    ticker=announcement.ticker.upper(),
                    company_name=announcement.company,
                    isin=announcement.isin,
                    market="AIM",
                )
                session.add(company)
                session.flush()
            else:
                company.company_name = announcement.company
                if announcement.isin:
                    company.isin = announcement.isin

            announcement_row = session.scalar(
                select(AnnouncementRow).where(
                    AnnouncementRow.source_id == announcement.source_id
                )
            )
            if announcement_row is None:
                announcement_row = AnnouncementRow(
                    company_id=company.id,
                    source_id=announcement.source_id,
                    published_at=announcement.published_at,
                    headline=announcement.title,
                    announcement_type=note.rns_type or announcement.rns_type,
                    source_url=announcement.source_url,
                    raw_text=announcement.text,
                    categories=announcement.categories,
                )
                session.add(announcement_row)
                session.flush()
            else:
                announcement_row.company_id = company.id
                announcement_row.published_at = announcement.published_at
                announcement_row.headline = announcement.title
                announcement_row.announcement_type = note.rns_type or announcement.rns_type
                announcement_row.source_url = announcement.source_url
                announcement_row.raw_text = announcement.text
                announcement_row.categories = announcement.categories

            session.execute(
                update(AnalystRunRow)
                .where(AnalystRunRow.announcement_id == announcement_row.id)
                .values(is_current=False)
            )

            run = AnalystRunRow(
                announcement_id=announcement_row.id,
                impact_colour=note.impact_colour,
                impact_score=note.impact_score,
                impact_level=note.impact_level,
                headline=note.headline,
                takeaway=note.takeaway,
                what_changed=note.what_changed.model_dump(mode="json"),
                analyst_view=note.analyst_view,
                supports_case=note.supports_case,
                challenges_case=note.challenges_case,
                watch_items=note.watch_items,
                source_warnings=note.source_warnings,
                confidence=note.confidence,
                prompt_version=prompt_version,
                model_version=model_version,
                analysis_version=ANALYSIS_VERSION,
                is_current=True,
            )
            session.add(run)
            session.flush()

            session.add_all(
                [
                    FactRow(
                        company_id=company.id,
                        announcement_id=announcement_row.id,
                        analyst_run_id=run.id,
                        label=fact.label,
                        metric=fact.metric,
                        period=fact.period,
                        value=fact.value,
                        unit=fact.unit,
                        basis=fact.basis,
                        note=fact.note,
                        comparator=fact.comparator,
                        previous_value=fact.previous_value,
                        information_status=fact.information_status,
                    )
                    for fact in note.key_facts
                ]
            )
            session.add_all(
                [
                    GuidanceEventRow(
                        company_id=company.id,
                        announcement_id=announcement_row.id,
                        analyst_run_id=run.id,
                        metric=event.metric,
                        period=event.period,
                        value=event.value,
                        status=event.status,
                        comparator=event.comparator,
                        note=event.note,
                    )
                    for event in note.guidance_events
                ]
            )
            session.add_all(
                [
                    ManagementClaimRow(
                        company_id=company.id,
                        announcement_id=announcement_row.id,
                        analyst_run_id=run.id,
                        claim=claim.claim,
                        target_date=claim.target_date,
                        status=claim.status,
                        outcome=claim.outcome,
                        evidence=claim.evidence,
                    )
                    for claim in note.management_claims
                ]
            )
            session.flush()

            return PersistedAnalysis(
                company_id=str(company.id),
                announcement_id=str(announcement_row.id),
                analyst_run_id=str(run.id),
                source_id=announcement.source_id,
                impact_colour=note.impact_colour,
                impact_level=note.impact_level,
                created_at=run.created_at,
            )

    def load_prior_context(
        self,
        ticker: str,
        *,
        before: datetime,
        limit: int = 40,
    ) -> list[dict[str, object]]:
        with session_scope(self.session_factory) as session:
            rows = session.execute(
                select(AnnouncementRow, AnalystRunRow)
                .join(CompanyRow, CompanyRow.id == AnnouncementRow.company_id)
                .join(
                    AnalystRunRow,
                    AnalystRunRow.announcement_id == AnnouncementRow.id,
                )
                .where(
                    CompanyRow.ticker == ticker.upper(),
                    AnnouncementRow.published_at < before,
                    AnalystRunRow.is_current.is_(True),
                )
                .order_by(desc(AnnouncementRow.published_at))
                .limit(limit)
            ).all()

            output: list[dict[str, object]] = []
            for announcement, run in reversed(rows):
                facts = session.scalars(
                    select(FactRow).where(FactRow.analyst_run_id == run.id)
                ).all()
                guidance = session.scalars(
                    select(GuidanceEventRow).where(
                        GuidanceEventRow.analyst_run_id == run.id
                    )
                ).all()
                output.append(
                    {
                        "source_id": announcement.source_id,
                        "published_at": announcement.published_at.isoformat(),
                        "title": announcement.headline,
                        "rns_type": announcement.announcement_type,
                        "impact_colour": run.impact_colour,
                        "impact_score": run.impact_score,
                        "headline": run.headline,
                        "takeaway": run.takeaway,
                        "what_changed": run.what_changed,
                        "analyst_view": run.analyst_view,
                        "facts": [
                            {
                                "label": fact.label,
                                "metric": fact.metric,
                                "period": fact.period,
                                "value": fact.value,
                                "unit": fact.unit,
                                "comparator": fact.comparator,
                                "previous_value": fact.previous_value,
                                "information_status": fact.information_status,
                            }
                            for fact in facts
                        ],
                        "guidance": [
                            {
                                "metric": event.metric,
                                "period": event.period,
                                "value": event.value,
                                "status": event.status,
                                "comparator": event.comparator,
                            }
                            for event in guidance
                        ],
                    }
                )
            return output

    def get_current_analysis(self, source_id: str) -> dict[str, Any] | None:
        with session_scope(self.session_factory) as session:
            row = session.execute(
                select(AnnouncementRow, CompanyRow, AnalystRunRow)
                .join(CompanyRow, CompanyRow.id == AnnouncementRow.company_id)
                .join(
                    AnalystRunRow,
                    AnalystRunRow.announcement_id == AnnouncementRow.id,
                )
                .where(
                    AnnouncementRow.source_id == source_id,
                    AnalystRunRow.is_current.is_(True),
                )
            ).first()
            if row is None:
                return None
            announcement, company, run = row
            return {
                "source_id": announcement.source_id,
                "ticker": company.ticker,
                "company": company.company_name,
                "published_at": announcement.published_at.isoformat(),
                "headline": run.headline,
                "impact_colour": run.impact_colour,
                "impact_level": run.impact_level,
                "source_warnings": run.source_warnings,
                "prompt_version": run.prompt_version,
                "model_version": run.model_version,
                "analysis_version": run.analysis_version,
            }
