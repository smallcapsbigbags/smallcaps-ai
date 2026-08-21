from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time
from urllib.parse import quote
from zoneinfo import ZoneInfo

import requests

LONDON = ZoneInfo("Europe/London")
MARKET_OPEN = time(8, 0)
MARKET_CLOSE = time(16, 30)


def yahoo_symbol(ticker: str) -> str:
    value = (ticker or "").upper().strip()
    if value.endswith(".L"):
        return value
    return f"{value.rstrip('.-')}.L"


def publication_london(published_at: datetime) -> datetime:
    if published_at.tzinfo is None:
        published_at = published_at.replace(tzinfo=LONDON)
    return published_at.astimezone(LONDON)


def reaction_phase(
    published_at: datetime,
    *,
    now_london: datetime | None = None,
) -> str:
    """Return pre-open, intraday, close or after-close for the reaction session."""

    now = now_london or datetime.now(LONDON)
    published = publication_london(published_at)

    if published.date() == now.date() and published.time() >= MARKET_CLOSE:
        return "after-close"
    if now.time() < MARKET_OPEN:
        return "pre-open"
    if now.time() < MARKET_CLOSE:
        return "intraday"
    return "close"


@dataclass(frozen=True)
class DayQuote:
    latest: float
    previous_close: float
    change_pct: float
    currency: str = "GBp"


class YahooPriceClient:
    """MVP market-reaction client ported from the RNS-Xray pricing layer.

    It measures the normal daily move versus the previous trading-session close. The
    number is market context, not a claim that a single RNS caused the entire move.
    """

    source_name = "Yahoo Finance chart"

    def __init__(self, timeout_seconds: int = 25) -> None:
        self.timeout_seconds = timeout_seconds

    def day_quote(self, ticker: str) -> DayQuote:
        symbol = yahoo_symbol(ticker)
        url = "https://query1.finance.yahoo.com/v8/finance/chart/" + quote(
            symbol, safe=""
        )
        response = requests.get(
            url,
            params={"range": "5d", "interval": "1d", "includePrePost": "false"},
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 Chrome/124 Safari/537.36"
                ),
                "Accept": "application/json,text/plain,*/*",
            },
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
        result = ((payload.get("chart") or {}).get("result") or [None])[0]
        if not result:
            raise RuntimeError("Yahoo chart returned no result")

        meta = result.get("meta") or {}
        latest = meta.get("regularMarketPrice")
        previous = meta.get("chartPreviousClose") or meta.get("previousClose")

        if latest is None:
            closes = (
                (((result.get("indicators") or {}).get("quote") or [{}])[0]).get(
                    "close", []
                )
            )
            valid = [float(value) for value in closes if value is not None]
            if valid:
                latest = valid[-1]
                if previous is None and len(valid) >= 2:
                    previous = valid[-2]

        latest_value = float(latest) if latest is not None else 0.0
        previous_value = float(previous) if previous is not None else 0.0
        if latest_value <= 0 or previous_value <= 0:
            raise RuntimeError("Yahoo chart did not provide a valid current/previous close")

        change = ((latest_value / previous_value) - 1.0) * 100.0
        return DayQuote(
            latest=round(latest_value, 4),
            previous_close=round(previous_value, 4),
            change_pct=round(change, 2),
        )
