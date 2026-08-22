from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from analyst.company_memory import build_company_memory
from analyst.evidence import dedupe_source_urls
from database.db import session_scope
from database.models import (
    AnalystRunRow,
    AnnouncementRow,
    CompanyRow,
    FactRow,
    GuidanceEventRow,
    ManagementClaimRow,
)


class CompanyIntelligenceRepository:
    """Read boundary for deterministic Company Intelligence and company memory."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self.session_factory = session_factory

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

    def get_company_intelligence(self, ticker: str) -> dict[str, Any] | None:
        clean_ticker = ticker.upper().strip().replace(".L", "").rstrip(".-")
        with session_scope(self.session_factory) as session:
            company = session.scalar(
                select(CompanyRow).where(CompanyRow.ticker == clean_ticker)
            )
            if company is None:
                return None

            rows = session.execute(
                select(AnnouncementRow, AnalystRunRow)
                .join(
                    AnalystRunRow,
                    AnalystRunRow.announcement_id == AnnouncementRow.id,
                )
                .where(
                    AnnouncementRow.company_id == company.id,
                    AnalystRunRow.is_current.is_(True),
                    AnalystRunRow.quality_status == "publishable",
                )
                .order_by(AnnouncementRow.published_at)
            ).all()
            run_ids = [run.id for _announcement, run in rows]
            facts_by_run = self._facts_by_run(session, run_ids)
            guidance_by_run = self._guidance_by_run(session, run_ids)
            claims_by_run = self._claims_by_run(session, run_ids)

            records: list[dict[str, object]] = []
            for announcement, run in rows:
                source_urls = dedupe_source_urls(
                    announcement.source_urls,
                    announcement.source_url,
                    run.source_references,
                )
                records.append(
                    {
                        "source_id": announcement.source_id,
                        "published_at": announcement.published_at.isoformat(),
                        "title": announcement.headline,
                        "source_url": source_urls[0] if source_urls else "",
                        "rns_type": announcement.announcement_type,
                        "impact_colour": run.impact_colour,
                        "impact_score": run.impact_score,
                        "impact_rationale": run.impact_rationale,
                        "headline": run.headline,
                        "takeaway": run.takeaway,
                        "new_information": list(run.new_information),
                        "reiterated_information": list(run.reiterated_information),
                        "what_changed": dict(run.what_changed),
                        "analyst_view": run.analyst_view,
                        "supports_case": list(run.supports_case),
                        "challenges_case": list(run.challenges_case),
                        "watch_items": list(run.watch_items),
                        "disclosure_assessment": dict(run.disclosure_assessment),
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
                                "basis": fact.basis,
                                "note": fact.note,
                                "comparator": fact.comparator,
                                "comparator_type": fact.comparator_type,
                                "comparator_source_id": fact.comparator_source_id,
                                "previous_value": fact.previous_value,
                                "information_status": fact.information_status,
                            }
                            for fact in facts_by_run.get(run.id, [])
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
                                "note": event.note,
                            }
                            for event in guidance_by_run.get(run.id, [])
                        ],
                        "management_claims": [
                            {
                                "claim": claim.claim,
                                "claim_key": claim.claim_key,
                                "metric": claim.metric,
                                "target_value": claim.target_value,
                                "target_date": claim.target_date,
                                "status": claim.status,
                                "outcome": claim.outcome,
                                "evidence": claim.evidence,
                            }
                            for claim in claims_by_run.get(run.id, [])
                        ],
                    }
                )

            snapshot = build_company_memory(
                records,
                ticker=company.ticker,
                company=company.company_name,
                before=datetime.now(timezone.utc),
            )
            return snapshot.model_dump(mode="json")
