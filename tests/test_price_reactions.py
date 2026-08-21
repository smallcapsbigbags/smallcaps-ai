from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

from market.pricing import DayQuote
from market.reactions import (
    DailyPriceReactionService,
    reaction_session_date,
    session_phase,
)

LONDON = ZoneInfo("Europe/London")


class FakeRepository:
    def __init__(self) -> None:
        self.upserts: list[dict[str, object]] = []

    def list_price_targets(self, *, published_after, published_before):
        return [
            {
                "source_id": "spr-1",
                "ticker": "SPR",
                "published_at": datetime(
                    2026, 8, 21, 7, 0, tzinfo=LONDON
                ),
            },
            {
                "source_id": "spr-2",
                "ticker": "SPR",
                "published_at": datetime(
                    2026, 8, 21, 7, 5, tzinfo=LONDON
                ),
            },
        ]

    def upsert_price_reaction(self, **kwargs):
        self.upserts.append(kwargs)
        return kwargs


class FakeClient:
    source_name = "recorded"

    def __init__(self) -> None:
        self.calls: list[str] = []

    def day_quote(self, ticker: str) -> DayQuote:
        self.calls.append(ticker)
        return DayQuote(
            latest=84.0,
            previous_close=80.0,
            change_pct=5.0,
        )


def test_reaction_session_moves_after_close_and_weekends() -> None:
    assert reaction_session_date(
        datetime(2026, 8, 21, 16, 31, tzinfo=LONDON)
    ) == date(2026, 8, 24)
    assert reaction_session_date(
        datetime(2026, 8, 22, 9, 0, tzinfo=LONDON)
    ) == date(2026, 8, 24)


def test_session_phase_uses_london_market_hours() -> None:
    day = date(2026, 8, 21)
    assert session_phase(
        day,
        now_london=datetime(2026, 8, 21, 7, 30, tzinfo=LONDON),
    ) == "pre-open"
    assert session_phase(
        day,
        now_london=datetime(2026, 8, 21, 12, 0, tzinfo=LONDON),
    ) == "intraday"
    assert session_phase(
        day,
        now_london=datetime(2026, 8, 21, 16, 45, tzinfo=LONDON),
    ) == "close"


def test_price_service_requests_once_per_ticker_and_updates_each_rns() -> None:
    repository = FakeRepository()
    client = FakeClient()
    service = DailyPriceReactionService(
        repository=repository,
        client=client,
    )

    result = service.run(
        now_london=datetime(2026, 8, 21, 12, 0, tzinfo=LONDON)
    )

    assert result.target_count == 2
    assert result.ticker_count == 1
    assert result.updated == 2
    assert client.calls == ["SPR"]
    assert {item["source_id"] for item in repository.upserts} == {
        "spr-1",
        "spr-2",
    }
    assert all(item["daily_change_pct"] == 5.0 for item in repository.upserts)


def test_pre_open_price_service_does_not_call_market_data() -> None:
    repository = FakeRepository()
    client = FakeClient()
    service = DailyPriceReactionService(
        repository=repository,
        client=client,
    )
    result = service.run(
        now_london=datetime(2026, 8, 21, 7, 30, tzinfo=LONDON)
    )
    assert result.pending == 2
    assert result.updated == 0
    assert client.calls == []
