from __future__ import annotations

from datetime import date, datetime
from functools import lru_cache
from zoneinfo import ZoneInfo

import exchange_calendars as xcals
import pandas as pd

LONDON = ZoneInfo("Europe/London")


@lru_cache(maxsize=1)
def london_exchange():
    return xcals.get_calendar("XLON")


def _label(day: date) -> pd.Timestamp:
    return pd.Timestamp(day.isoformat())


def is_trading_session(day: date) -> bool:
    return bool(london_exchange().is_session(_label(day)))


def session_on_or_after(day: date) -> date:
    calendar = london_exchange()
    label = _label(day)
    if calendar.is_session(label):
        return day
    return calendar.date_to_session(label, direction="next").date()


def next_trading_session(day: date) -> date:
    calendar = london_exchange()
    return calendar.date_to_session(_label(day) + pd.Timedelta(days=1), direction="next").date()


def session_bounds_london(day: date) -> tuple[datetime, datetime]:
    if not is_trading_session(day):
        raise ValueError(f"{day.isoformat()} is not an LSE trading session")
    calendar = london_exchange()
    label = _label(day)
    opened = calendar.session_open(label).tz_convert(LONDON).to_pydatetime()
    closed = calendar.session_close(label).tz_convert(LONDON).to_pydatetime()
    return opened, closed
