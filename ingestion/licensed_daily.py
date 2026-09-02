from __future__ import annotations

import hashlib
from datetime import date, datetime
from typing import Any
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

import requests

from ingestion.investegate_daily import CatalogueAnnouncement
from ingestion.multi_source_daily import MultiSourceDailyAIMSource, _announcement_key

LONDON = ZoneInfo("Europe/London")


class LicensedDailyAIMSource(MultiSourceDailyAIMSource):
    """A configurable licensed AIM catalogue with existing evidence retrieval."""

    name = "Configured licensed AIM catalogue · authoritative evidence retrieval"

    def __init__(
        self,
        *,
        feed_url: str,
        feed_token: str = "",
        feed_timeout_seconds: int = 30,
        **kwargs: object,
    ) -> None:
        super().__init__(**kwargs)
        self.feed_url = feed_url.strip()
        self.feed_token = feed_token.strip()
        self.feed_timeout_seconds = max(5, int(feed_timeout_seconds))
        parsed = urlparse(self.feed_url)
        local_http = (
            parsed.scheme == "http"
            and parsed.hostname in {"localhost", "127.0.0.1", "::1"}
        )
        if not (
            parsed.netloc
            and (parsed.scheme == "https" or local_http)
        ):
            raise ValueError(
                "Licensed AIM feed URL must use HTTPS "
                "(HTTP is allowed only for localhost tests)."
            )

    @staticmethod
    def _records(payload: Any) -> list[dict[str, Any]]:
        if isinstance(payload, list):
            return [item for item in payload if isinstance(item, dict)]
        if not isinstance(payload, dict):
            return []
        for key in ("records", "announcements", "items", "data"):
            value = payload.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
        return []

    @staticmethod
    def _value(row: dict[str, Any], *keys: str) -> Any:
        for key in keys:
            value = row.get(key)
            if value not in (None, ""):
                return value
        return None

    @classmethod
    def _published_at(cls, row: dict[str, Any]) -> datetime:
        raw = cls._value(
            row,
            "published_at",
            "publishedAt",
            "released_at",
            "releasedAt",
            "timestamp",
            "datetime",
        )
        if raw is None:
            raise ValueError("published_at is required")
        if isinstance(raw, datetime):
            value = raw
        else:
            text = str(raw).strip().replace("Z", "+00:00")
            value = datetime.fromisoformat(text)
        if value.tzinfo is None:
            value = value.replace(tzinfo=LONDON)
        return value.astimezone(LONDON)

    @staticmethod
    def _categories(value: Any) -> list[str]:
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        if isinstance(value, str):
            return [
                item.strip()
                for item in value.split(",")
                if item.strip()
            ]
        return []

    def _parse_record(
        self,
        row: dict[str, Any],
        *,
        day: date,
    ) -> CatalogueAnnouncement | None:
        published_at = self._published_at(row)
        if published_at.date() != day:
            return None

        ticker = str(
            self._value(row, "ticker", "tidm", "symbol") or ""
        ).strip().upper().replace(".L", "").rstrip(".-")
        title = str(
            self._value(row, "title", "headline", "announcement_title") or ""
        ).strip()
        company = str(
            self._value(row, "company", "company_name", "issuer") or ticker
        ).strip()
        source_url = str(
            self._value(row, "source_url", "url", "announcement_url") or ""
        ).strip()
        if not ticker:
            raise ValueError("ticker is required")
        if not title:
            raise ValueError("headline/title is required")
        if not self._valid_url(source_url):
            raise ValueError("a valid source_url is required")

        identity = _announcement_key(
            ticker=ticker,
            published_at=published_at,
            headline=title,
        )
        source_id = "aim-licensed-" + hashlib.sha256(
            identity.encode()
        ).hexdigest()[:24]
        return CatalogueAnnouncement(
            source_id=source_id,
            ticker=ticker,
            company=company or ticker,
            published_at=published_at,
            title=title,
            source_url=source_url,
            categories=self._categories(row.get("categories")),
        )

    def list_announcements(
        self,
        day: date,
    ) -> tuple[list[CatalogueAnnouncement], list[str]]:
        self._evidence, self._urls, self._notes = {}, {}, {}
        self._resolved_companies = {}

        headers = {"Accept": "application/json"}
        if self.feed_token:
            headers["Authorization"] = f"Bearer {self.feed_token}"
        try:
            response = self.session.get(
                self.feed_url,
                headers=headers,
                timeout=self.feed_timeout_seconds,
            )
            response.raise_for_status()
            payload = response.json()
        except (requests.RequestException, ValueError) as exc:
            raise RuntimeError(
                f"Licensed AIM catalogue request failed: {exc}"
            ) from exc

        output: dict[str, CatalogueAnnouncement] = {}
        invalid = 0
        wrong_day = 0
        for row in self._records(payload):
            try:
                item = self._parse_record(row, day=day)
            except (TypeError, ValueError):
                invalid += 1
                continue
            if item is None:
                wrong_day += 1
                continue
            key = self._catalogue_key(item)
            output[key] = item
            self._urls[item.source_id] = [item.source_url]

        items = sorted(output.values(), key=lambda item: item.published_at)
        items = self._reuse_existing_source_ids(items)
        warnings = [
            "Licensed AIM catalogue "
            f"accepted={len(items)} invalid={invalid} other_date={wrong_day}."
        ]
        if not items:
            warnings.append(
                f"Licensed AIM catalogue returned no valid rows dated {day.isoformat()}."
            )
        return items, warnings
