from __future__ import annotations

import hashlib
import json
import re
from datetime import date, datetime
from urllib.parse import urljoin, urlparse
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup
from pydantic import Field

from analyst.models import AnnouncementInput, StrictModel


class CatalogueAnnouncement(StrictModel):
    """Deterministic catalogue metadata discovered before AI evidence retrieval."""

    source_id: str
    ticker: str
    company: str
    published_at: datetime
    title: str
    source_url: str
    categories: list[str] = Field(default_factory=list)


class DeepItem(StrictModel):
    source_id: str
    evidence: str
    source_urls: list[str] = Field(default_factory=list)
    source_note: str = ""


class DeepBatch(StrictModel):
    records: list[DeepItem]


class InvestegateDailyAIMSource:
    """Current RNS-Xray Daily AIM source, ported into Smallcaps.ai.

    Discovery is deterministic: read today's AIM catalogue from Investegate.
    OpenAI web search is used only after discovery to retrieve dense source
    evidence for the exact announcements already identified.
    """

    name = "Investegate AIM catalogue · OpenAI evidence retrieval"
    base_url = "https://www.investegate.co.uk"
    aim_url = "https://www.investegate.co.uk/aim"

    def __init__(
        self,
        *,
        api_key: str,
        deep_model: str,
        deep_batch_size: int = 5,
        max_document_chars: int = 45_000,
        max_pages: int = 8,
        timeout_seconds: int = 45,
    ) -> None:
        if not api_key:
            raise ValueError("OPENAI_API_KEY is required for Daily AIM ingestion")

        from openai import OpenAI

        self.client = OpenAI(api_key=api_key, timeout=180, max_retries=1)
        self.deep_model = deep_model
        self.deep_batch_size = max(1, deep_batch_size)
        self.max_document_chars = max_document_chars
        self.max_pages = max(1, max_pages)
        self.timeout_seconds = timeout_seconds
        self._evidence: dict[str, str] = {}
        self._urls: dict[str, str] = {}
        self._notes: dict[str, str] = {}
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Accept": "text/html,application/xhtml+xml",
                "Accept-Language": "en-GB,en;q=0.9",
                "User-Agent": "Mozilla/5.0 SmallcapsAI-DailyRNS/0.5",
            }
        )

    def list_announcements(
        self, day: date
    ) -> tuple[list[CatalogueAnnouncement], list[str]]:
        """Read Investegate's AIM catalogue and return exact rows for *day*."""

        self._evidence, self._urls, self._notes = {}, {}, {}
        output: dict[str, CatalogueAnnouncement] = {}
        found_day = False

        for page in range(1, self.max_pages + 1):
            url = self.aim_url if page == 1 else f"{self.aim_url}?page={page}"
            try:
                response = self.session.get(url, timeout=self.timeout_seconds)
                response.raise_for_status()
            except requests.RequestException as exc:
                raise RuntimeError(
                    f"Investegate AIM catalogue request failed: {exc}"
                ) from exc

            rows = self._parse_page(response.text)
            if not rows:
                if page == 1:
                    raise RuntimeError(
                        "Investegate AIM catalogue returned no announcement rows"
                    )
                break

            row_dates = [published.date() for published, *_ in rows]
            for published, ticker, company, headline, source_url in rows:
                if published.date() != day:
                    continue
                found_day = True
                published_at = published.replace(
                    tzinfo=ZoneInfo("Europe/London")
                )
                identity = source_url or (
                    f"{ticker}|{published_at.isoformat()}|{headline}"
                )
                source_id = (
                    "aim-" + hashlib.sha256(identity.encode()).hexdigest()[:24]
                )
                item = CatalogueAnnouncement(
                    source_id=source_id,
                    ticker=ticker,
                    company=company,
                    published_at=published_at,
                    title=headline,
                    source_url=source_url,
                )
                output[source_id] = item
                self._urls[source_id] = source_url

            if min(row_dates) < day:
                break

        warnings = [
            "Owner-test MVP: today's AIM catalogue is read directly from Investegate; OpenAI web search is used only after discovery for evidence retrieval and analysis.",
            "Investegate may publish a filtered set of announcements. Commercial display rights must be confirmed before public production use.",
        ]
        if not found_day:
            warnings.append(
                f"Investegate returned no AIM rows dated {day.isoformat()} at the time of this check."
            )
        return sorted(output.values(), key=lambda item: item.published_at), warnings

    @classmethod
    def _parse_page(
        cls, html: str
    ) -> list[tuple[datetime, str, str, str, str]]:
        """Parse the same Investegate table structure used by RNS-Xray Daily."""

        soup = BeautifulSoup(html, "html.parser")
        ticker_re = re.compile(r"\(([^()]{1,20})\)\s*$")
        rows: list[tuple[datetime, str, str, str, str]] = []

        for row in soup.find_all("tr"):
            cells = row.find_all(["td", "th"])
            if len(cells) < 4:
                continue
            if cells[1].get_text(" ", strip=True).upper() != "RNS":
                continue
            try:
                published = datetime.strptime(
                    cells[0].get_text(" ", strip=True), "%d %b %Y %I:%M %p"
                )
            except ValueError:
                continue

            company_text = cells[2].get_text(" ", strip=True)
            match = ticker_re.search(company_text)
            if not match:
                continue
            ticker = (
                match.group(1)
                .strip()
                .upper()
                .replace(".L", "")
                .rstrip(".-")
            )
            company = ticker_re.sub("", company_text).strip() or ticker
            anchor = cells[3].find("a", href=True)
            if anchor is None:
                continue
            headline = anchor.get_text(" ", strip=True)
            if not headline:
                continue
            source_url = urljoin(cls.base_url, str(anchor.get("href")))
            rows.append((published, ticker, company, headline, source_url))

        return rows

    def prepare_documents(
        self, announcements: list[CatalogueAnnouncement]
    ) -> list[str]:
        """Use OpenAI web search to build evidence dossiers for known RNS rows."""

        for start in range(0, len(announcements), self.deep_batch_size):
            batch = announcements[start : start + self.deep_batch_size]
            payload = [
                {
                    "source_id": item.source_id,
                    "ticker": item.ticker,
                    "company": item.company,
                    "published_at": item.published_at.isoformat(),
                    "headline": item.title,
                    "source_url": item.source_url,
                }
                for item in batch
            ]
            prompt = f"""Retrieve dense factual source evidence for each exact AIM regulatory announcement below. Start with the supplied Investegate URL where available, then prefer issuer IR and official LSE/RNS pages for corroboration. Match company, ticker, headline and date. Preserve all disclosed financial, guidance, fundraising, contract, M&A, ownership and director-dealing numbers. Never infer missing facts. Return source_id exactly plus evidence and strongest source URLs.\n\nANNOUNCEMENTS:\n{json.dumps(payload, ensure_ascii=False)}"""

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
                    text_format=DeepBatch,
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
                continue

            valid_ids = {item.source_id for item in batch}
            for result in response.output_parsed.records:
                if result.source_id not in valid_ids:
                    continue
                if result.evidence.strip():
                    self._evidence[result.source_id] = result.evidence.strip()
                if result.source_note:
                    self._notes[result.source_id] = result.source_note.strip()
                best = next(
                    (url for url in result.source_urls if self._valid_url(url)), ""
                )
                if best:
                    self._urls[result.source_id] = best

        if not announcements:
            return []
        return [
            f"Targeted OpenAI evidence retrieval ran for {len(announcements)} new AIM announcement(s)."
        ]

    def fetch_document(self, announcement: CatalogueAnnouncement) -> AnnouncementInput:
        """Convert one discovered RNS plus its evidence dossier to Analyst input."""

        evidence = self._evidence.get(announcement.source_id, "").strip()
        if not evidence:
            evidence = (
                f"Regulatory announcement: {announcement.title}. "
                "No usable source evidence was returned."
            )
        note = self._notes.get(announcement.source_id, "")
        source_warning = (
            "Investegate catalogue plus OpenAI web-search evidence dossier used for Daily AIM MVP analysis; verify material facts against the original RNS."
            + (f" {note}" if note else "")
        )
        text = evidence[: self.max_document_chars]
        if source_warning:
            text += f"\n\nSOURCE NOTE: {source_warning[:700]}"

        return AnnouncementInput(
            source_id=announcement.source_id,
            ticker=announcement.ticker,
            company=announcement.company,
            published_at=announcement.published_at,
            title=announcement.title,
            text=text,
            source_url=self._urls.get(
                announcement.source_id, announcement.source_url
            ),
            categories=announcement.categories,
        )

    @staticmethod
    def _valid_url(value: str) -> bool:
        parsed = urlparse((value or "").strip())
        return parsed.scheme in {"http", "https"} and bool(parsed.netloc)
