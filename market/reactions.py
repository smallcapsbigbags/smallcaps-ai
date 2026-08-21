from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Protocol
from zoneinfo import ZoneInfo

from market.pricing import (
    MARKET_CLOSE,
    MARKET_OPEN,
    DayQuote,
    YahooPriceClient,
    publication_london,
)

LONDON = ZoneInfo("Europe/London")


class PriceReactionRepository(Protocol):
    def list_price_targets(
        self,
        *,
        published_after: datetime,
        published_before: datetime,
    ) -> list[dict[str, object]]: ...

    def upsert_price_reaction(
        self,
        *,
        source_id: str,
        reaction_session: str,
        phase: str,
        previous_close: float,
        latest_price: float,
        daily_change_pct: float,
        currency: str,
        source: str,
        observed_at: datetime,
    ) -> dict[str, object]: ...


class PriceClient(Protocol):
    source_name: str

    def day_quote(self, ticker: str) -> DayQuote: ...


def next_weekday(day: date) -> date:
    candidate = day + timedelta(days=1)
    while candidate.weekday() >= 5:
        candidate += timedelta(days=1)
    return candidate


def reaction_session_date(published_at: datetime) -> date:
    published = publication_london(published_at)
    day = published.date()
    if day.weekday() >= 5:
        while day.weekday() >= 5:
            day += timedelta(days=1)
        return day
    if published.time() >= MARKET_CLOSE:
        return next_weekday(day)
    return day


def session_phase(
    session_day: date,
    *,
    now_london: datetime | None = None,
) -> str:
    now = now_london or datetime.now(LONDON)
    if now.date() < session_day:
        return "pending"
    if now.date() > session_day:
        return "close"
    if now.time() < MARKET_OPEN:
        return "pre-open"
    if now.time() < MARKET_CLOSE:
        return "intraday"
    return "close"


@dataclass
class PriceUpdateResult:
    target_count: int = 0
    ticker_count: int = 0
    updated: int = 0
    pending: int = 0
    failed: int = 0
    warnings: list[str] = field(default_factory=list)


class DailyPriceReactionService:
    """Attach the market's daily move without changing the original AI Impact."""

    def __init__(
        self,
        *,
        repository: PriceReactionRepository,
        client: PriceClient | None = None,
    ) -> None:
        self.repository = repository
        self.client = client or YahooPriceClient()

    def run(
        self,
        *,
        now_london: datetime | None = None,
    ) -> PriceUpdateResult:
        now = now_london or datetime.now(LONDON)
        start = (now - timedelta(days=8)).astimezone(timezone.utc)
        end = (now + timedelta(days=1)).astimezone(timezone.utc)
        targets = self.repository.list_price_targets(
            published_after=start,
            published_before=end,
        )
        eligible = [
            target
            for target in targets
            if reaction_session_date(target["published_at"]) == now.date()
        ]
        result = PriceUpdateResult(target_count=len(eligible))
        if not eligible:
            return result

        phase = session_phase(now.date(), now_london=now)
        if phase in {"pending", "pre-open"}:
            result.pending = len(eligible)
            return result

        by_ticker: dict[str, list[dict[str, object]]] = {}
        for target in eligible:
            by_ticker.setdefault(str(target["ticker"]), []).append(target)
        result.ticker_count = len(by_ticker)

        observed_at = now.astimezone(timezone.utc)
        for ticker, ticker_targets in by_ticker.items():
            try:
                quote = self.client.day_quote(ticker)
            except Exception as exc:
                result.failed += len(ticker_targets)
                result.warnings.append(
                    f"{ticker}: market data failed: {type(exc).__name__}: {exc}"
                )
                continue

            for target in ticker_targets:
                self.repository.upsert_price_reaction(
                    source_id=str(target["source_id"]),
                    reaction_session=now.date().isoformat(),
                    phase=phase,
                    previous_close=quote.previous_close,
                    latest_price=quote.latest,
                    daily_change_pct=quote.change_pct,
                    currency=quote.currency,
                    source=self.client.source_name,
                    observed_at=observed_at,
                )
                result.updated += 1
        return result
