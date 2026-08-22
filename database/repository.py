from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Any

from sqlalchemy import Select, desc, select, update
from sqlalchemy.orm import Session, sessionmaker

from analyst.evidence import dedupe_source_urls
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
        values = dict(
            company_id=company.id,
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
        if row is None:
            row = AnnouncementRow(source_id=announcement.source_id, **values)
            session.add(row)
            session.flush()
        else:
            for key, value in values.items():
                setattr(row, key, value)
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
        announcement: AnnouncementRow,
        run: AnalystRunRow,
        note: AnalystNote,
    ) -> list[FactRow]:
        return [
            FactRow(
                company_id=company.id,
                announcement_id=announcement.id,
                analyst_run_id=run.id,
                ordinal=ordinal,
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
            for ordinal, fact in enumerate(note.key_facts)
        ]

    @staticmethod
    def _guidance_rows(
        company: CompanyRow,
        announcement: AnnouncementRow,
        run: AnalystRunRow,
        note: AnalystNote,
    ) -> list[GuidanceEventRow]:
        return [
            GuidanceEventRow(
                company_id=company.id,
                announcement_id=announcement.id,
                analyst_run_id=run.id,
                ordinal=ordinal,
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
            for ordinal, event in enumerate(note.guidance_events)
        ]

    @staticmethod
    def _claim_rows(
        company: CompanyRow,
        announcement: AnnouncementRow,
        run: AnalystRunRow,
        note: AnalystNote,
    ) -> list[ManagementClaimRow]:
        return [
            ManagementClaimRow(
                company_id=company.id,
                announcement_id=announcement.id,
                analyst_run_id=run.id,
                ordinal=ordinal,
                claim=claim.claim,
                claim_key=claim.claim_key,
                metric=claim.metric,
                target_value=claim.target_value,
                target_date=claim.target_date,
                status=claim.status,
                outcome=claim.outcome,
                evidence=claim.evidence,
            )
            for ordinal, claim in enumerate(note.management_claims)
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
            session.add_all(self._fact_rows(company, announcement_row, run, note))
            session.add_all(
                self._guidance_rows(company, announcement_row, run, note)
            )
            session.add_all(self._claim_rows(company, announcement_row, run, note))
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
            .order_by(FactRow.analyst_run_id, FactRow.ordinal, FactRow.created_at)
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
    def _claims_by_run(
        session: Session,
        run_ids: list[object],
    ) -> dict[object, list[ManagementClaimRow]]:
        output: dict[object, list[ManagementClaimRow]] = defaultdict(list)
        if not run_ids:
            return output
        rows = session.scalars(
            select(ManagementClaimRow)
            .where(ManagementClaimRow.analyst_run_id.in_(run_ids))
            .order_by(
                ManagementClaimRow.analyst_run_id,
                ManagementClaimRow.ordinal,
                ManagementClaimRow.created_at,
            )
        ).all()
        for row in rows:
            output[row.analyst_run_id].append(row)
        return output

    @staticmethod
    def _fact_context(fact: FactRow) -> dict[str, object]:
        return {
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
            "basis": fact.basis,
            "note": fact.note,
            "comparator": fact.comparator,
            "comparator_type": fact.comparator_type,
            "comparator_source_id": fact.comparator_source_id,
            "previous_value": fact.previous_value,
            "information_status": fact.information_status,
        }

    @staticmethod
    def _guidance_context(event: GuidanceEventRow) -> dict[str, object]:
        return {
            "metric": event.metric,
            "period": event.period,
            "value": event.value,
            "status": event.status,
            "comparator": event.comparator,
            "previous_value": event.previous_value,
            "previous_source_id": event.previous_source_id,
            "information_status": event.information_status,
            "note": event.note,
        }

    @staticmethod
    def _claim_context(claim: ManagementClaimRow) -> dict[str, object]:
        return {
            "claim": claim.claim,
            "claim_key": claim.claim_key,
            "metric": claim.metric,
            "target_value": claim.target_value,
            "target_date": claim.target_date,
            "status": claim.status,
            "outcome": claim.outcome,
            "evidence": claim.evidence,
        }

    def load_prior_context(
        self,
        ticker: str,
        *,
        before: datetime,
        limit: int = 120,
    ) -> list[dict[str, object]]:
        """Load eligible point-in-time history for memory and delta analysis.

        Facts, guidance and management claims are bulk-loaded in three queries so
        a mature 12-month company history does not create hundreds of database
        round trips for every new RNS.
        """

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
            if not rows:
                return []

            chronological = list(reversed(rows))
            run_ids = [run.id for _announcement, run in chronological]
            facts_by_run = self._facts_by_run(session, run_ids)
            guidance_by_run = self._guidance_by_run(session, run_ids)
            claims_by_run = self._claims_by_run(session, run_ids)

            output: list[dict[str, object]] = []
            for announcement, run in chronological:
                source_urls = dedupe_source_urls(
                    announcement.source_urls,
                    announcement.source_url,
                    run.source_references,
                )
                output.append(
                    {
                        "source_id": announcement.source_id,
                        "published_at": announcement.published_at.isoformat(),
                        "title": announcement.headline,
                        "source_url": source_urls[0] if source_urls else "",
                        "source_urls": source_urls,
                        "rns_type": announcement.announcement_type,
                        "impact_colour": run.impact_colour,
                        "impact_score": run.impact_score,
                        "impact_rationale": run.impact_rationale,
                        "headline": run.headline,
                        "takeaway": run.takeaway,
                        "new_information": list(run.new_information),
                        "reiterated_information": list(
                            run.reiterated_information
                        ),
                        "what_changed": dict(run.what_changed),
                        "analyst_view": run.analyst_view,
                        "supports_case": list(run.supports_case),
                        "challenges_case": list(run.challenges_case),
                        "watch_items": list(run.watch_items),
                        "disclosure_assessment": dict(
                            run.disclosure_assessment
                        ),
                        "facts": [
                            self._fact_context(fact)
                            for fact in facts_by_run.get(run.id, [])
                        ],
                        "guidance": [
                            self._guidance_context(event)
                            for event in guidance_by_run.get(run.id, [])
                        ],
                        "management_claims": [
                            self._claim_context(claim)
                            for claim in claims_by_run.get(run.id, [])
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
