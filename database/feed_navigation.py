from __future__ import annotations

from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from database.db import session_scope
from database.models import AnalystRunRow, AnnouncementRow

LONDON = ZoneInfo("Europe/London")


def _as_london_day(value: datetime | None) -> date | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(LONDON).date()


def latest_publishable_day(
    session_factory: sessionmaker[Session],
) -> date | None:
    """Return the latest date that can actually populate the public Feed.

    The Feed should open on the latest available AIM session rather than an empty
    weekend or bank-holiday date. This query uses the same current/publishable
    boundary as the public product.
    """

    with session_scope(session_factory) as session:
        latest = session.scalar(
            select(func.max(AnnouncementRow.published_at))
            .join(
                AnalystRunRow,
                AnalystRunRow.announcement_id == AnnouncementRow.id,
            )
            .where(
                AnalystRunRow.is_current.is_(True),
                AnalystRunRow.quality_status == "publishable",
            )
        )
    return _as_london_day(latest)
