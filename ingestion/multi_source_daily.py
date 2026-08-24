from __future__ import annotations

import hashlib
import json
import re
from datetime import date, datetime, timedelta, timezone
from urllib.parse import urljoin
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup
from pydantic import Field
from sqlalchemy import select

from analyst.models import StrictModel
from database.db import session_scope
from database.models import AnnouncementRow, CompanyRow
from database.repository import IntelligenceRepository
from ingestion.investegate_daily import CatalogueAnnouncement, InvestegateDailyAIMSource

LONDON = ZoneInfo("Europe/London")


class VerifiedEvidenceItem(StrictModel):
    source_id: str
    company: str = ""
    evidence: str
    source_urls: list[str] = Field(default_factory=list)
    source_note: str = ""


class VerifiedEvidenceBatch(StrictModel):
    records: list[VerifiedEvidenceItem]


def _clean(value: object) -> str:
    return " ".join(str(value or "").strip().split())


def _headline_key(value: object) -> str:
    return " ".join(re.sub(r"[^a-z0-9]+", " ", _clean(value).lower()).split())


def _announcement_key(*, ticker: str, published_at: datetime, headline: str) -> str:
    aware = published_at
    if aware.tzinfo is None:
        aware = aware.replace(tzinfo=LONDON)
    utc_minute = aware.astimezone(timezone.utc).replace(second=0, microsecond=0)
    return f"{ticker.strip().upper()}|{utc_minute.isoformat()}|{_headline_key(headline)}"


class MultiSourceDailyAIMSource(InvestegateDailyAIMSource):
    """AIM discovery from Investegate with LSE.co.uk cross-check/fallback.

    Investegate remains the normal discovery authority because it supplies the
    established AIM catalogue used by Smallcaps.ai. LSE.co.uk is independently
    parsed to corroborate matching rows and becomes the automatic catalogue
    fallback only when Investegate is unavailable or empty. Unmatched LSE rows
    are deliberately held out while Investegate is healthy because the live LSE
    page can contain a broader instrument universe than the desired AIM-company
    feed. Exact announcements are then researched with source priority given to
    issuer IR, FCA NSM and official LSE/RNS material.
    """

    name = "Investegate AIM catalogue · LSE.co.uk cross-check/fallback · authoritative evidence retrieval"
    lse_base_url = "https://www.lse.co.uk"
    lse_aim_url = "https://www.lse.co.uk/rns/aim.html"
    fca_nsm_url = "https://data.fca.org.uk/#/nsm/nationalstoragemechanism"

    def __init__(
        self,
        *,
        repository: IntelligenceRepository | None = None,
        **kwargs: object,
    ) -> None:
        super().__init__(**kwargs)
        self.repository = repository
        self._resolved_companies: dict[str, str] = {}

    @staticmethod
    def _catalogue_key(item: CatalogueAnnouncement) -> str:
        return _announcement_key(
            ticker=item.ticker,
            published_at=item.published_at,
            headline=item.title,
        )

    @classmethod
    def _parse_lse_page(
        cls, html: str
    ) -> tuple[date | None, list[tuple[datetime, str, str, str]]]:
        """Parse one LSE.co.uk AIM page, accepting only rows whose Source is RNS."""

        soup = BeautifulSoup(html, "html.parser")
        text = soup.get_text(" ", strip=True)
        date_match = re.search(
            r"\b(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),\s+"
            r"(\d{1,2}\s+[A-Za-z]+\s+\d{4})\b",
            text,
        )
        page_date: date | None = None
        if date_match:
            try:
                page_date = datetime.strptime(date_match.group(1), "%d %B %Y").date()
            except ValueError:
                page_date = None

        rows: list[tuple[datetime, str, str, str]] = []
        if page_date is None:
            return None, rows

        for row in soup.find_all("tr"):
            cells = row.find_all(["td", "th"])
            if len(cells) < 4:
                continue
            if cells[1].get_text(" ", strip=True).upper() != "RNS":
                continue
            time_text = cells[0].get_text(" ", strip=True).lower()
            try:
                parsed_time = datetime.strptime(time_text, "%I:%M %p").time()
            except ValueError:
                continue

            ticker = (
                cells[2]
                .get_text(" ", strip=True)
                .upper()
                .replace(".L", "")
                .rstrip(".-")
            )
            if not ticker:
                continue
            anchor = cells[3].find("a", href=True)
            if anchor is None:
                continue
            headline = anchor.get_text(" ", strip=True)
            if not headline:
                continue
            source_url = urljoin(cls.lse_base_url, str(anchor.get("href")))
            rows.append(
                (datetime.combine(page_date, parsed_time), ticker, headline, source_url)
            )

        return page_date, rows

    def _list_lse(self, day: date) -> list[CatalogueAnnouncement]:
        output: dict[str, CatalogueAnnouncement] = {}

        for page in range(1, self.max_pages + 1):
            url = self.lse_aim_url if page == 1 else f"{self.lse_aim_url}?page={page}"
            try:
                response = self.session.get(url, timeout=self.timeout_seconds)
                response.raise_for_status()
            except requests.RequestException as exc:
                raise RuntimeError(f"LSE.co.uk AIM catalogue request failed: {exc}") from exc

            page_date, rows = self._parse_lse_page(response.text)
            if page_date is None:
                if page == 1:
                    raise RuntimeError("LSE.co.uk AIM catalogue page date could not be parsed")
                break
            if page_date < day:
                break
            if page_date > day:
                continue

            for published, ticker, headline, source_url in rows:
                published_at = published.replace(tzinfo=LONDON)
                key = _announcement_key(
                    ticker=ticker,
                    published_at=published_at,
                    headline=headline,
                )
                source_id = "aim-lse-" + hashlib.sha256(key.encode()).hexdigest()[:20]
                output[key] = CatalogueAnnouncement(
                    source_id=source_id,
                    ticker=ticker,
                    company=ticker,
                    published_at=published_at,
                    title=headline,
                    source_url=source_url,
                )

        return sorted(output.values(), key=lambda item: item.published_at)

    def _existing_ids_by_key(
        self, items: list[CatalogueAnnouncement]
    ) -> dict[str, str]:
        """Find an already-stored identity for a catalogue alias.

        PostgreSQL preserves timezone-aware timestamps while SQLite drops the
        offset in tests. The candidate query is therefore deliberately wider
        than the final match. The exact ticker + UTC minute + headline fingerprint
        below remains the dedupe authority, so widening this window cannot merge
        unrelated announcements.
        """

        if self.repository is None or not items:
            return {}

        tickers = sorted({item.ticker.upper() for item in items})
        utc_times = [
            item.published_at.astimezone(timezone.utc)
            if item.published_at.tzinfo is not None
            else item.published_at.replace(tzinfo=LONDON).astimezone(timezone.utc)
            for item in items
        ]
        start = min(utc_times) - timedelta(hours=2)
        end = max(utc_times) + timedelta(hours=2)
        output: dict[str, str] = {}

        with session_scope(self.repository.session_factory) as session:
            rows = session.execute(
                select(
                    AnnouncementRow.source_id,
                    AnnouncementRow.published_at,
                    AnnouncementRow.headline,
                    CompanyRow.ticker,
                )
                .join(CompanyRow, AnnouncementRow.company_id == CompanyRow.id)
                .where(
                    CompanyRow.ticker.in_(tickers),
                    AnnouncementRow.published_at >= start,
                    AnnouncementRow.published_at <= end,
                )
            ).all()

        for source_id, published_at, headline, ticker in rows:
            key = _announcement_key(
                ticker=str(ticker),
                published_at=published_at,
                headline=str(headline),
            )
            output.setdefault(key, str(source_id))
        return output

    def _known_company_names(self, tickers: set[str]) -> dict[str, str]:
        if self.repository is None or not tickers:
            return {}
        with session_scope(self.repository.session_factory) as session:
            rows = session.execute(
                select(CompanyRow.ticker, CompanyRow.company_name).where(
                    CompanyRow.ticker.in_(sorted(tickers))
                )
            ).all()
        return {str(ticker).upper(): _clean(company) for ticker, company in rows}

    def _reuse_existing_source_ids(
        self, items: list[CatalogueAnnouncement]
    ) -> list[CatalogueAnnouncement]:
        existing = self._existing_ids_by_key(items)
        known_companies = self._known_company_names(
            {item.ticker.upper() for item in items if item.company == item.ticker}
        )

        output: list[CatalogueAnnouncement] = []
        for item in items:
            key = self._catalogue_key(item)
            source_id = existing.get(key, item.source_id)
            company = item.company
            if company == item.ticker:
                company = known_companies.get(item.ticker.upper(), company)

            if source_id != item.source_id:
                urls = self._urls.pop(item.source_id, [])
                current = self._urls.get(source_id, [])
                self._urls[source_id] = list(dict.fromkeys([*current, *urls]))

            if source_id != item.source_id or company != item.company:
                item = item.model_copy(
                    update={"source_id": source_id, "company": company}
                )
            output.append(item)
        return output

    def list_announcements(
        self, day: date
    ) -> tuple[list[CatalogueAnnouncement], list[str]]:
        self._evidence, self._urls, self._notes = {}, {}, {}
        self._resolved_companies = {}
        warnings: list[str] = []

        investegate_items: list[CatalogueAnnouncement] = []
        investegate_error = ""
        try:
            investegate_items, investegate_warnings = super().list_announcements(day)
            warnings.extend(
                warning
                for warning in investegate_warnings
                if warning.startswith("Investegate returned no AIM rows")
            )
        except Exception as exc:
            investegate_error = f"{type(exc).__name__}: {exc}"
            self._evidence, self._urls, self._notes = {}, {}, {}

        lse_items: list[CatalogueAnnouncement] = []
        lse_error = ""
        try:
            lse_items = self._list_lse(day)
        except Exception as exc:
            lse_error = f"{type(exc).__name__}: {exc}"

        if investegate_error and lse_error:
            raise RuntimeError(
                "All AIM catalogue sources failed. "
                f"Investegate={investegate_error}; LSE.co.uk={lse_error}"
            )
        if lse_error:
            warnings.append(
                "LSE.co.uk AIM cross-check unavailable; Investegate discovery "
                "remains active. " + lse_error[:350]
            )

        # Normal path: Investegate is the discovery authority. LSE augments matching
        # rows with a second catalogue URL, but unmatched LSE rows are held out rather
        # than automatically widening the AIM universe.
        if investegate_items:
            merged: dict[str, CatalogueAnnouncement] = {
                self._catalogue_key(item): item for item in investegate_items
            }
            investegate_keys = set(merged)
            lse_keys = {self._catalogue_key(item) for item in lse_items}
            lse_by_key = {self._catalogue_key(item): item for item in lse_items}

            for key in investegate_keys & lse_keys:
                primary = merged[key]
                lse_item = lse_by_key[key]
                existing_urls = self._urls.get(primary.source_id, [])
                self._urls[primary.source_id] = list(
                    dict.fromkeys([*existing_urls, lse_item.source_url])
                )

            lse_only = len(lse_keys - investegate_keys)
            investegate_only = len(investegate_keys - lse_keys)
            if lse_items and (lse_only or investegate_only):
                warnings.append(
                    "AIM catalogue cross-check differs: "
                    f"Investegate={len(investegate_items)}, "
                    f"LSE.co.uk RNS={len(lse_items)}, "
                    f"LSE-only held out={lse_only}, "
                    f"Investegate-only={investegate_only}. "
                    "Investegate remains the discovery authority while healthy."
                )
            elif not lse_items and not lse_error:
                warnings.append(
                    "LSE.co.uk returned no RNS rows for the target day; "
                    "Investegate discovery remains active."
                )

            items = sorted(merged.values(), key=lambda item: item.published_at)
            return self._reuse_existing_source_ids(items), warnings

        # Fallback path: Investegate either failed or returned no rows. In that case
        # LSE.co.uk is allowed to supply the catalogue rather than leaving the feed
        # blind. The subsequent evidence stage still verifies exact company/date/title.
        if lse_items:
            if investegate_error:
                warnings.append(
                    "Investegate AIM discovery unavailable; LSE.co.uk RNS catalogue "
                    "is being used as the fallback. " + investegate_error[:350]
                )
            else:
                warnings.append(
                    "Investegate returned no rows for the target day; "
                    "LSE.co.uk RNS catalogue is being used as the fallback."
                )
            for item in lse_items:
                self._urls[item.source_id] = [item.source_url] if item.source_url else []
            return self._reuse_existing_source_ids(lse_items), warnings

        # Neither catalogue yielded rows, but at least one source returned normally.
        if investegate_error:
            warnings.append("Investegate discovery failed and LSE.co.uk returned no target-day RNS rows.")
        return [], warnings

    def prepare_documents(
        self, announcements: list[CatalogueAnnouncement]
    ) -> list[str]:
        """Retrieve evidence with issuer/FCA/official RNS sources ahead of mirrors."""

        for start in range(0, len(announcements), self.deep_batch_size):
            batch = announcements[start : start + self.deep_batch_size]
            payload = [
                {
                    "source_id": item.source_id,
                    "ticker": item.ticker,
                    "company": item.company,
                    "published_at": item.published_at.isoformat(),
                    "headline": item.title,
                    "catalogue_urls": self._urls.get(item.source_id, [])
                    or ([item.source_url] if item.source_url else []),
                }
                for item in batch
            ]
            prompt = f"""Retrieve dense factual source evidence for each exact AIM regulatory announcement below. Match company/ticker, headline and date; do not substitute a similarly named announcement.

SOURCE PRIORITY FOR VERIFICATION:
1. Issuer investor-relations / official company announcement.
2. FCA National Storage Mechanism (NSM), {self.fca_nsm_url}, especially for exact-company verification and historical regulated disclosures.
3. Official London Stock Exchange / RNS publication pages.
4. The supplied Investegate and LSE.co.uk catalogue/announcement URLs as secondary discovery mirrors and corroboration.

Use web search to locate the strongest accessible primary source. The catalogue URLs identify the target announcement but do not outrank an issuer, FCA NSM or official LSE/RNS source. Preserve all disclosed financial, guidance, fundraising, contract, M&A, ownership and director-dealing numbers. Never infer missing facts. If an authoritative source cannot be accessed, say so in source_note and use the strongest corroborated evidence available. Return source_id exactly, the canonical company name, dense evidence, and strongest source URLs in priority order.

ANNOUNCEMENTS:
{json.dumps(payload, ensure_ascii=False)}"""

            try:
                response = self.client.responses.parse(
                    model=self.deep_model,
                    tools=[
                        {
                            "type": "web_search",
                            "search_context_size": "high",
                            "user_location": {
                                "type": "approximate",
                                "country": "GB",
                                "timezone": "Europe/London",
                            },
                        }
                    ],
                    input=prompt,
                    text_format=VerifiedEvidenceBatch,
                    max_output_tokens=18_000,
                    store=False,
                )
            except Exception as exc:
                for item in batch:
                    self._notes[item.source_id] = (
                        f"Targeted evidence retrieval failed: {exc}"[:500]
                    )
                continue

            if response.output_parsed is None:
                for item in batch:
                    self._notes[item.source_id] = (
                        "Targeted evidence retrieval returned no structured result."
                    )
                continue

            valid_ids = {item.source_id for item in batch}
            returned_ids: set[str] = set()
            for result in response.output_parsed.records:
                if result.source_id not in valid_ids:
                    continue
                returned_ids.add(result.source_id)
                if result.company.strip():
                    self._resolved_companies[result.source_id] = result.company.strip()
                if result.evidence.strip():
                    self._evidence[result.source_id] = result.evidence.strip()
                if result.source_note:
                    self._notes[result.source_id] = result.source_note.strip()
                urls = [url for url in result.source_urls if self._valid_url(url)]
                existing = self._urls.get(result.source_id, [])
                self._urls[result.source_id] = list(dict.fromkeys([*urls, *existing]))

            for item in batch:
                if item.source_id not in returned_ids:
                    self._notes[item.source_id] = (
                        "Targeted evidence retrieval omitted this source ID."
                    )

        if not announcements:
            return []
        return [
            f"Authoritative evidence retrieval ran for {len(announcements)} new AIM "
            "announcement(s), with issuer/FCA NSM/official RNS sources prioritised."
        ]

    def fetch_document(self, announcement: CatalogueAnnouncement):
        company = self._resolved_companies.get(announcement.source_id, "").strip()
        if company and (
            announcement.company == announcement.ticker or not announcement.company.strip()
        ):
            announcement = announcement.model_copy(update={"company": company})
        return super().fetch_document(announcement)
