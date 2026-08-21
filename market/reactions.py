from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Protocol
from zoneinfo import ZoneInfo

from market.calendar import is_trading_session, next_trading_session, session_bounds_london, session_on_or_after
from market.pricing import DayQuote, YahooPriceClient, publication_london

LONDON = ZoneInfo("Europe/London")


class PriceReactionRepository(Protocol):
    def list_price_targets(self, *, published_after: datetime, published_before: datetime) -> list[dict[str, object]]: ...
    def upsert_price_reaction(self, *, source_id: str, reaction_session: str, phase: str, previous_close: float, latest_price: float, daily_change_pct: float, currency: str, source: str, observed_at: datetime) -> dict[str, object]: ...


class PriceClient(Protocol):
    source_name: str
    def day_quote(self, ticker: str) -> DayQuote: ...


def reaction_session_date(published_at: datetime) -> date:
    published = publication_london(published_at)
    day = published.date()
    session_day = session_on_or_after(day)
    if session_day != day:
        return session_day
    _opened, closed = session_bounds_london(day)
    if published >= closed:
        return next_trading_session(day)
    return day


def session_phase(session_day: date, *, now_london: datetime | None = None) -> str:
    now = now_london or datetime.now(LONDON)
    if not is_trading_session(session_day):
        raise ValueError(f"{session_day.isoformat()} is not an LSE trading session")
    if now.date() < session_day:
        return "pending"
    if now.date() > session_day:
        return "close"
    opened, closed = session_bounds_london(session_day)
    if now < opened:
        return "pre-open"
    if now < closed:
        return "intraday"
    return "close"


@dataclass
class PriceUpdateResult:
    target_count: int = 0
    ticker_count: int = 0
    updated: int = 0
    pending: int = 0
    stale: int = 0
    failed: int = 0
    warnings: list[str] = field(default_factory=list)


class DailyPriceReactionService:
    def __init__(self, *, repository: PriceReactionRepository, client: PriceClient | None = None) -> None:
        self.repository = repository
        self.client = client or YahooPriceClient()

    def run(self, *, now_london: datetime | None = None) -> PriceUpdateResult:
        now = now_london or datetime.now(LONDON)
        start = (now - timedelta(days=14)).astimezone(timezone.utc)
        end = (now + timedelta(days=1)).astimezone(timezone.utc)
        targets = self.repository.list_price_targets(published_after=start, published_before=end)
        current: list[dict[str, object]] = []
        stale: list[dict[str, object]] = []
        for target in targets:
            session_day = reaction_session_date(target["published_at"])
            has_frozen_close = bool(target.get("has_frozen_close"))
            if session_day == now.date():
                current.append(target)
            elif session_day < now.date() and not has_frozen_close:
                stale.append(target)
        result = PriceUpdateResult(target_count=len(current), stale=len(stale))
        if stale:
            result.warnings.append(f"{len(stale)} announcement reaction(s) missed their closing session and require historical-price recovery.")
        if not current:
            return result
        phase = session_phase(now.date(), now_london=now)
        if phase in {"pending", "pre-open"}:
            result.pending = len(current)
            return result
        by_ticker: dict[str, list[dict[str, object]]] = {}
        for target in current:
            by_ticker.setdefault(str(target["ticker"]), []).append(target)
        result.ticker_count = len(by_ticker)
        observed_at = now.astimezone(timezone.utc)
        for ticker, ticker_targets in by_ticker.items():
            try:
                quote = self.client.day_quote(ticker)
            except Exception as exc:
                result.failed += len(ticker_targets)
                result.warnings.append(f"{ticker}: market data failed: {type(exc).__name__}: {exc}")
                continue
            for target in ticker_targets:
                self.repository.upsert_price_reaction(source_id=str(target["source_id"]), reaction_session=now.date().isoformat(), phase=phase, previous_close=quote.previous_close, latest_price=quote.latest, daily_change_pct=quote.change_pct, currency=quote.currency, source=self.client.source_name, observed_at=observed_at)
                result.updated += 1
        return result
