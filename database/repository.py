from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import Select, desc, select, update
from sqlalchemy.orm import Session, sessionmaker

from analyst.models import (
    AnalystNote,
    AnnouncementInput,
    PersistedAnalysis,
    QualityReport,
)
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

    @staticmethod
    def _company_by_ticker(ticker: str) -> Select[tuple[CompanyRow]]:
        return select(CompanyRow).where(CompanyRow.ticker == ticker.upper())

    def _upsert_company(
        self,
        session: Session,
        announcement: AnnouncementInput,
    ) -> CompanyRow:
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
            return company

        company.company_name = announcement.company
        if announcement.isin:
            company.isin = announcement.isin
        return company

    @staticmethod
    def _apply_announcement_fields(
        row: AnnouncementRow,
        company: CompanyRow,
        announcement: AnnouncementInput,
        note: AnalystNote,
    ) -> None:
        row.company_id = company.id
        row.published_at = announcement.published_at
        row.headline = announcement.title
        row.announcement_type = note.rns_type or announcement.rns_type
        row.source_url = announcement.source_url
        row.source_urls = announcement.source_urls
        row.source_note = announcement.source_note
        row.evidence_status = announcement.evidence_status
        row.evidence_retrieved_at = announcement.evidence_retrieved_at
        row.raw_text = announcement.text
        row.categories = announcement.categories

    def _upsert_announcement(
        self,
        session: Session,
        company: CompanyRow,
        announcement: AnnouncementInput,
        note: AnalystNote,
    ) -> AnnouncementRow:
        row = session.scalar(
            select(AnnouncementRow).where(
                AnnouncementRow.source_id == announcement.source_id
            )
        )
        if row is None:
            row = AnnouncementRow(
                company_id=company.id,
                source_id=announcement.source_id,
                published_at=announcement.published_at,
                headline=announcement.title,
                announcement_type=note.rns_type or announcement.rns_type,
                source_url=announcement.source_url,
                source_urls=announcement.source_urls,
                source_note=announcement.source_note,
                evidence_status=announcement.evidence_status,
                evidence_retrieved_at=announcement.evidence_retrieved_at,
                raw_text=announcement.text,
                categories=announcement.categories,
            )
            session.add(row)
            session.flush()
            return row

        self._apply_announcement_fields(row, company, announcement, note)
        return row

    @staticmethod
    def _build_run(
        announcement_row: AnnouncementRow,
        note: AnalystNote,
        quality: QualityReport,
        *,
        prompt_version: str,
        model_version: str,
    ) -> AnalystRunRow:
        return AnalystRunRow(
            announcement_id=announcement_row.id,
            impact_colour=note.impact_colour,
            impact_score=note.impact_score,
            impact_level=note.impact_level,
            impact_rationale=note.impact_rationale,
            impact_drivers=[
                driver.model_dump(mode="json") for driver in note.impact_drivers
            ],
            headline=note.headline,
            takeaway=note.takeaway,
            new_information=note.new_information,
            reiterated_information=note.reiterated_information,
            what_changed=note.what_changed.model_dump(mode="json"),
            analyst_view=note.analyst_view,
            supports_case=note.supports_case,
            challenges_case=note.challenges_case,
            watch_items=note.watch_items,
            disclosure_assessment=note.disclosure_assessment.model_dump(mode="json"),
            source_references=note.source_references,
            source_warnings=note.source_warnings,
            quality_status=quality.status,
            quality_flags=[flag.model_dump(mode="json") for flag in quality.flags],
            confidence=note.confidence,
            prompt_version=prompt_version,
            model_version=model_version,
            analysis_version=ANALYSIS_VERSION,
            is_current=True,
        )

    @staticmethod
    def _fact_rows(
        company: CompanyRow,
        announcement_row: AnnouncementRow,
        run: AnalystRunRow,
        note: AnalystNote,
    ) -> list[FactRow]:
        return [
            FactRow(
                company_id=company.id,
                announcement_id=announcement_row.id,
                analyst_run_id=run.id,
                label=fact.label,
                metric=fact.metric,
                period=fact.period,
                value=fact.value,
                unit=fact.unit,
                currency=fact.currency,
                as_of_date=fact.as_of_date,
                value_numeric=fact.value_numeric,
                value_low=fact.value_low,
                value_high=fact.value_high,
                basis=fact.basis,
                note=fact.note,
                comparator=fact.comparator,
                comparator_type=fact.comparator_type,
                comparator_source_id=fact.comparator_source_id,
                previous_value=fact.previous_value,
                information_status=fact.information_status,
            )
            for fact in note.key_facts
        ]

    @staticmethod
    def _guidance_rows(
        company: CompanyRow,
        announcement_row: AnnouncementRow,
        run: AnalystRunRow,
        note: AnalystNote,
    ) -> list[GuidanceEventRow]:
        return [
            GuidanceEventRow(
                company_id=company.id,
                announcement_id=announcement_row.id,
                analyst_run_id=run.id,
                metric=event.metric,
                period=event.period,
                value=event.value,
                status=event.status,
                comparator=event.comparator,
                previous_value=event.previous_value,
                previous_source_id=event.previous_source_id,
                information_status=event.information_status,
                note=event.note,
            )
            for event in note.guidance_events
        ]

    @staticmethod
    def _claim_rows(
        company: CompanyRow,
        announcement_row: AnnouncementRow,
        run: AnalystRunRow,
        note: AnalystNote,
    ) -> list[ManagementClaimRow]:
        return [
            ManagementClaimRow(
                company_id=company.id,
                announcement_id=announcement_row.id,
                analyst_run_id=run.id,
                claim=claim.claim,
                claim_key=claim.claim_key,
                metric=claim.metric,
                target_value=claim.target_value,
                target_date=claim.target_date,
                status=claim.status,
                outcome=claim.outcome,
                evidence=claim.evidence,
            )
            for claim in note.management_claims
        ]

    def save_analysis(
        self,
        announcement: AnnouncementInput,
        note: AnalystNote,
        *,
        prompt_version: str,
        model_version: str,
        quality_report: QualityReport | None = None,
    ) -> PersistedAnalysis:
        if note.source_id != announcement.source_id:
            raise ValueError(
                "AnalystNote source_id must match the announcement source_id"
            )

        quality = quality_report or QualityReport(status="publishable")

        with session_scope(self.session_factory) as session:
            company = self._upsert_company(session, announcement)
            announcement_row = self._upsert_announcement(
                session,
                company,
                announcement,
                note,
            )

            session.execute(
                update(AnalystRunRow)
                .where(AnalystRunRow.announcement_id == announcement_row.id)
                .values(is_current=False)
            )

            run = self._build_run(
                announcement_row,
                note,
                quality,
                prompt_version=prompt_version,
                model_version=model_version,
            )
            session.add(run)
            session.flush()

            session.add_all(
                self._fact_rows(company, announcement_row, run, note)
            )
            session.add_all(
                self._guidance_rows(company, announcement_row, run, note)
            )
            session.add_all(
                self._claim_rows(company, announcement_row, run, note)
            )
            session.flush()

            return PersistedAnalysis(
                company_id=str(company.id),
                announcement_id=str(announcement_row.id),
                analyst_run_id=str(run.id),
                source_id=announcement.source_id,
                impact_colour=note.impact_colour,
                impact_level=note.impact_level,
                quality_status=quality.status,
                quality_flags=quality.flags,
                created_at=run.created_at,
            )

    def load_prior_context(
        self,
        ticker: str,
        *,
        before: datetime,
        limit: int = 40,
    ) -> list[dict[str, object]]:
        """Return only current, publishable, point-in-time company context."""

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
                    AnalystRunRow.quality_status == "publishable",
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
                        "impact_rationale": run.impact_rationale,
                        "headline": run.headline,
                        "takeaway": run.takeaway,
                        "new_information": run.new_information,
                        "reiterated_information": run.reiterated_information,
                        "what_changed": run.what_changed,
                        "analyst_view": run.analyst_view,
                        "disclosure_assessment": run.disclosure_assessment,
                        "facts": [
                            {
                                "label": fact.label,
                                "metric": fact.metric,
                                "period": fact.period,
                                "value": fact.value,
                                "unit": fact.unit,
                                "currency": fact.currency,
                                "as_of_date": fact.as_of_date,
                                "value_numeric": fact.value_numeric,
                                "value_low": fact.value_low,
                                "value_high": fact.value_high,
                                "comparator": fact.comparator,
                                "comparator_type": fact.comparator_type,
                                "comparator_source_id": fact.comparator_source_id,
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
                                "previous_value": event.previous_value,
                                "previous_source_id": event.previous_source_id,
                                "information_status": event.information_status,
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
                "impact_rationale": run.impact_rationale,
                "quality_status": run.quality_status,
                "quality_flags": run.quality_flags,
                "source_references": run.source_references,
                "source_warnings": run.source_warnings,
                "prompt_version": run.prompt_version,
                "model_version": run.model_version,
                "analysis_version": run.analysis_version,
            }
