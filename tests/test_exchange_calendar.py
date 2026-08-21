from datetime import date, datetime
from zoneinfo import ZoneInfo

from market.calendar import is_trading_session, session_on_or_after
from market.reactions import reaction_session_date, session_phase

LONDON = ZoneInfo("Europe/London")


def test_lse_calendar_moves_bank_holiday_to_next_session() -> None:
    assert is_trading_session(date(2026, 8, 31)) is False
    assert session_on_or_after(date(2026, 8, 31)) == date(2026, 9, 1)
    assert reaction_session_date(datetime(2026, 8, 31, 9, 0, tzinfo=LONDON)) == date(2026, 9, 1)


def test_after_close_uses_next_official_lse_session() -> None:
    assert reaction_session_date(datetime(2026, 8, 21, 16, 31, tzinfo=LONDON)) == date(2026, 8, 24)


def test_session_phase_uses_exchange_open_and_close() -> None:
    day = date(2026, 8, 21)
    assert session_phase(day, now_london=datetime(2026, 8, 21, 7, 30, tzinfo=LONDON)) == "pre-open"
    assert session_phase(day, now_london=datetime(2026, 8, 21, 12, 0, tzinfo=LONDON)) == "intraday"
    assert session_phase(day, now_london=datetime(2026, 8, 21, 16, 45, tzinfo=LONDON)) == "close"
