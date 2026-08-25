from __future__ import annotations

import hashlib
from datetime import datetime, timedelta

from sqlalchemy import desc, func, or_, select
from sqlalchemy.orm import Session, sessionmaker

from analyst.classification import canonical_rns_type, classify_metadata_type
from analyst.models import AnnouncementInput
from database.db import session_scope
from database.models import AnalystRunRow, AnnouncementRow, CompanyRow, FactRow
from database.triage_models import AnnouncementTriageRow
from ingestion.investegate_daily import CatalogueAnnouncement
from ingestion.triage import TRIAGE_VERSION, TriageDecision


class TriageRepository:
    """Persist every catalogue row independently from full analyst publication."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self.session_factory = session_factory

    @staticmethod
    def _upsert_company(
        session: Session,
        *,
        ticker: str,
        company_name: str,
        isin: str = "",
    ) -> CompanyRow:
        ticker = ticker.upper().strip()
        company = session.scalar(select(CompanyRow).where(CompanyRow.ticker == ticker))
        if company is None:
            company = CompanyRow(
                ticker=ticker,
                company_name=company_name or ticker,
                isin=isin,
                market="AIM",
            )
            session.add(company)
            session.flush()
            return company
        if company_name and company_name != ticker:
            company.company_name = company_name
        if isin:
            company.isin = isin
        return company

    @staticmethod
    def _upsert_announcement(
        session: Session,
        company: CompanyRow,
        announcement: AnnouncementInput,
        *,
        announcement_type: str,
    ) -> AnnouncementRow:
        row = session.scalar(
            select(AnnouncementRow).where(
                AnnouncementRow.source_id == announcement.source_id
            )
        )
        values = {
            "company_id": company.id,
            "published_at": announcement.published_at,
            "headline": announcement.title,
            "announcement_type": announcement_type,
            "source_url": announcement.source_url,
            "source_urls": announcement.source_urls,
            "source_note": announcement.source_note,
            "evidence_status": announcement.evidence_status,
            "evidence_retrieved_at": announcement.evidence_retrieved_at,
            "raw_text": announcement.text,
            "categories": announcement.categories,
        }
        if row is None:
            row = AnnouncementRow(source_id=announcement.source_id, **values)
            session.add(row)
            session.flush()
        else:
            for key, value in values.items():
                setattr(row, key, value)
        return row

    @staticmethod
    def _hash_catalogue(item: CatalogueAnnouncement) -> str:
        payload = "|".join(
            [
                item.source_id,
                item.ticker.upper(),
                item.published_at.isoformat(),
                item.title.strip(),
                item.source_url.strip(),
                *[str(value).strip() for value in item.categories],
            ]
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    @staticmethod
    def _hash_evidence(text: str) -> str:
        clean = text.strip()
        return hashlib.sha256(clean.encode("utf-8")).hexdigest() if clean else ""

    @staticmethod
    def _metadata_input(item: CatalogueAnnouncement, *, reason: str) -> AnnouncementInput:
        return AnnouncementInput(
            source_id=item.source_id,
            ticker=item.ticker,
            company=item.company,
            published_at=item.published_at,
            title=item.title,
            text=f"Regulatory announcement catalogue record: {item.title}.",
            source_url=item.source_url,
            source_urls=[item.source_url] if item.source_url else [],
            source_note=reason,
            evidence_status="metadata-only",
            rns_type=classify_metadata_type(item),
            categories=item.categories,
        )

    def record_catalogue(
        self,
        item: CatalogueAnnouncement,
        decision: TriageDecision,
    ) -> None:
        announcement = self._metadata_input(item, reason=decision.reason)
        self._persist(
            announcement,
            decision,
            announcement_type=classify_metadata_type(item),
            source_hash=self._hash_catalogue(item),
        )

    def record_document(
        self,
        announcement: AnnouncementInput,
        decision: TriageDecision,
    ) -> None:
        self._persist(
            announcement,
            decision,
            announcement_type=canonical_rns_type(announcement, announcement.rns_type),
            evidence_hash=self._hash_evidence(announcement.text),
        )

    def update_decision(
        self,
        source_id: str,
        decision: TriageDecision,
    ) -> None:
        with session_scope(self.session_factory) as session:
            row = session.scalar(
                select(AnnouncementTriageRow)
                .join(AnnouncementRow, AnnouncementRow.id == AnnouncementTriageRow.announcement_id)
                .where(AnnouncementRow.source_id == source_id)
            )
            if row is None:
                raise LookupError(f"Missing triage row for {source_id}")
            self._apply_decision(row, decision)

    def _persist(
        self,
        announcement: AnnouncementInput,
        decision: TriageDecision,
        *,
        announcement_type: str,
        source_hash: str = "",
        evidence_hash: str = "",
    ) -> None:
        with session_scope(self.session_factory) as session:
            company = self._upsert_company(
                session,
                ticker=announcement.ticker,
                company_name=announcement.company,
                isin=announcement.isin,
            )
            announcement_row = self._upsert_announcement(
                session,
                company,
                announcement,
                announcement_type=announcement_type,
            )
            row = session.scalar(
                select(AnnouncementTriageRow).where(
                    AnnouncementTriageRow.announcement_id == announcement_row.id
                )
            )
            if row is None:
                row = AnnouncementTriageRow(
                    announcement_id=announcement_row.id,
                    triage_class=decision.triage_class,
                    triage_reason=decision.reason,
                    processing_level=decision.processing_level,
                    triage_version=TRIAGE_VERSION,
                )
                session.add(row)
            self._apply_decision(row, decision)
            if source_hash:
                row.source_hash = source_hash
            if evidence_hash:
                row.evidence_hash = evidence_hash

    @staticmethod
    def _apply_decision(row: AnnouncementTriageRow, decision: TriageDecision) -> None:
        row.triage_class = decision.triage_class
        row.triage_reason = decision.reason
        row.processing_level = decision.processing_level
        row.triage_version = TRIAGE_VERSION
        row.metadata_score = int(decision.score)
        row.escalated = bool(decision.escalated)
        row.escalation_reason = decision.escalation_reason
        row.light_facts = list(decision.light_facts)

    def company_context(self, ticker: str, *, before: datetime) -> dict[str, object]:
        """Return only deterministic context required by the LIGHT escalation rules."""

        start = before - timedelta(days=180)
        with session_scope(self.session_factory) as session:
            recent = session.execute(
                select(AnnouncementRow, AnalystRunRow)
                .join(CompanyRow, CompanyRow.id == AnnouncementRow.company_id)
                .outerjoin(
                    AnalystRunRow,
                    (AnalystRunRow.announcement_id == AnnouncementRow.id)
                    & AnalystRunRow.is_current.is_(True),
                )
                .where(
                    CompanyRow.ticker == ticker.upper(),
                    AnnouncementRow.published_at < before,
                    AnnouncementRow.published_at >= start,
                )
                .order_by(desc(AnnouncementRow.published_at))
                .limit(80)
            ).all()

            director_count = 0
            adverse = False
            for announcement, run in recent:
                text = f"{announcement.announcement_type} {announcement.headline}".lower()
                if "director dealing" in text or "pdmr" in text:
                    director_count += 1
                if any(term in text for term in ("profit warning", "downgrade", "trading update")):
                    if run is None or run.impact_colour == "red":
                        adverse = True

            revenue = self._latest_fact(
                session,
                ticker=ticker,
                before=before,
                patterns=("%revenue%", "%sales%"),
            )
            shares = self._latest_fact(
                session,
                ticker=ticker,
                before=before,
                patterns=("%shares in issue%", "%total voting rights%", "%issued share capital%"),
            )

        return {
            "recent_director_dealings": director_count,
            "recent_adverse_trading": adverse,
            "latest_revenue_value": revenue,
            "latest_share_count_value": shares,
        }

    @staticmethod
    def _latest_fact(
        session: Session,
        *,
        ticker: str,
        before: datetime,
        patterns: tuple[str, ...],
    ) -> str:
        predicates = []
        for pattern in patterns:
            predicates.extend(
                [
                    func.lower(FactRow.metric).like(pattern),
                    func.lower(FactRow.label).like(pattern),
                ]
            )
        row = session.execute(
            select(FactRow)
            .join(CompanyRow, CompanyRow.id == FactRow.company_id)
            .join(AnnouncementRow, AnnouncementRow.id == FactRow.announcement_id)
            .join(AnalystRunRow, AnalystRunRow.id == FactRow.analyst_run_id)
            .where(
                CompanyRow.ticker == ticker.upper(),
                AnnouncementRow.published_at < before,
                AnalystRunRow.is_current.is_(True),
                AnalystRunRow.quality_status == "publishable",
                FactRow.basis.in_(("reported", "calculated")),
                or_(*predicates),
            )
            .order_by(desc(AnnouncementRow.published_at), FactRow.ordinal)
            .limit(1)
        ).scalar_one_or_none()
        if row is None:
            return ""
        return row.value
