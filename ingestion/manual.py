from __future__ import annotations

import hashlib
from datetime import datetime, timezone

from analyst.models import AnnouncementInput


def normalise_ticker(value: str) -> str:
    ticker = (value or "").upper().strip().replace(".L", "").rstrip(".-")
    if not ticker:
        raise ValueError("Ticker is required")
    if len(ticker) > 24:
        raise ValueError("Ticker is too long")
    return ticker


def build_manual_announcement(
    *,
    ticker: str,
    company: str,
    published_at: datetime,
    title: str,
    text: str,
    source_url: str = "",
    rns_type: str = "Other",
    categories: list[str] | None = None,
    source_id: str = "",
    isin: str = "",
) -> AnnouncementInput:
    clean_ticker = normalise_ticker(ticker)
    clean_title = (title or "").strip()
    clean_text = (text or "").strip()
    clean_url = source_url.strip()
    if not clean_title:
        raise ValueError("Announcement title is required")
    if not clean_text:
        raise ValueError("Announcement text is required")

    if published_at.tzinfo is None:
        raise ValueError("published_at must be timezone-aware")

    if not source_id:
        identity = "|".join(
            [
                clean_ticker,
                published_at.isoformat(),
                clean_title,
                clean_url,
            ]
        )
        source_id = (
            "manual-"
            + hashlib.sha256(identity.encode("utf-8")).hexdigest()[:24]
        )

    return AnnouncementInput(
        source_id=source_id,
        ticker=clean_ticker,
        company=(company or clean_ticker).strip(),
        published_at=published_at,
        title=clean_title,
        text=clean_text,
        source_url=clean_url,
        source_urls=[clean_url] if clean_url else [],
        source_note="Manual QA/recovery ingestion.",
        evidence_status="complete",
        evidence_retrieved_at=datetime.now(timezone.utc),
        rns_type=rns_type.strip() or "Other",
        categories=categories or [],
        isin=isin.strip(),
    )
