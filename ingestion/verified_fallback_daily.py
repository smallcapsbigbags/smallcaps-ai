from __future__ import annotations

from sqlalchemy import select

from database.db import session_scope
from database.models import AnnouncementRow, CompanyRow
from ingestion.investegate_daily import CatalogueAnnouncement
from ingestion.multi_source_daily import MultiSourceDailyAIMSource


class VerifiedFallbackDailyAIMSource(MultiSourceDailyAIMSource):
    """Fail-closed wrapper for LSE-only discovery fallback.

    When Investegate is healthy, the parent source already keeps unmatched LSE rows
    out of automated discovery. If Investegate is unavailable/empty, this wrapper
    admits only tickers previously observed through a non-LSE AIM catalogue identity.
    Unknown LSE tickers are held out rather than broadening the market universe.
    """

    name = "Investegate AIM catalogue · verified LSE.co.uk fallback · authoritative evidence retrieval"

    def _verified_aim_tickers(self) -> set[str]:
        if self.repository is None:
            return set()
        with session_scope(self.repository.session_factory) as session:
            rows = session.execute(
                select(CompanyRow.ticker)
                .join(AnnouncementRow, AnnouncementRow.company_id == CompanyRow.id)
                .where(
                    AnnouncementRow.source_id.like("aim-%"),
                    ~AnnouncementRow.source_id.like("aim-lse-%"),
                )
                .distinct()
            ).scalars().all()
        return {str(ticker).strip().upper() for ticker in rows if str(ticker).strip()}

    @staticmethod
    def _using_lse_fallback(warnings: list[str]) -> bool:
        return any(
            "LSE.co.uk RNS catalogue is being used as the fallback" in warning
            for warning in warnings
        )

    def list_announcements(
        self, day
    ) -> tuple[list[CatalogueAnnouncement], list[str]]:
        items, warnings = super().list_announcements(day)
        if not items or not self._using_lse_fallback(warnings):
            return items, warnings

        verified = self._verified_aim_tickers()
        accepted = [item for item in items if item.ticker.upper() in verified]
        held = [item for item in items if item.ticker.upper() not in verified]

        for item in held:
            self._urls.pop(item.source_id, None)
            self._evidence.pop(item.source_id, None)
            self._notes.pop(item.source_id, None)

        warnings.append(
            "LSE fallback safety: "
            f"accepted={len(accepted)} previously verified AIM ticker row(s), "
            f"held out={len(held)} unverified LSE ticker row(s). "
            "Unknown tickers require later verification rather than automatic publication."
        )
        return accepted, warnings
