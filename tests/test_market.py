from __future__ import annotations

from datetime import datetime

from market.pricing import LONDON, reaction_phase, yahoo_symbol


def test_market_reaction_phases_use_london_time() -> None:
    published = datetime(2026, 8, 21, 7, 0, tzinfo=LONDON)
    assert reaction_phase(
        published,
        now_london=datetime(2026, 8, 21, 7, 30, tzinfo=LONDON),
    ) == "pre-open"
    assert reaction_phase(
        published,
        now_london=datetime(2026, 8, 21, 12, 0, tzinfo=LONDON),
    ) == "intraday"
    assert reaction_phase(
        published,
        now_london=datetime(2026, 8, 21, 16, 45, tzinfo=LONDON),
    ) == "close"


def test_yahoo_symbol_normalisation() -> None:
    assert yahoo_symbol("SPR") == "SPR.L"
    assert yahoo_symbol("spr.l") == "SPR.L"
