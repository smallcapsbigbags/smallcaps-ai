from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import desc, select
from sqlalchemy.orm import Session, sessionmaker

from database.db import session_scope
from database.models import AnalystRunRow, AnnouncementRow
from product.daily_editor import resolve_editor_cutoff

LONDON = ZoneInfo("Europe/London")


def latest_full_analysis_day(
    session_factory: sessionmaker[Session],
    *,
    on_or_before: date,
    edition_state: str | None = None,
    cutoff: time | None = None,
) -> date | None:
    """Return the latest day containing a candidate for the selected edition.

    The query uses the same publication-safety conditions as the Daily editor.
    Timestamp filtering is completed in Europe/London so the selected day and
    edition cutoff remain correct on both PostgreSQL and SQLite.
    """

    _state, resolved_cutoff = resolve_editor_cutoff(
        edition_state=edition_state,
        cutoff=cutoff,
    )
    end = datetime.combine(
        on_or_before + timedelta(days=1),
        time.min,
        tzinfo=LONDON,
    ).astimezone(timezone.utc)

    with session_scope(session_factory) as session:
        published_values = session.scalars(
            select(AnnouncementRow.published_at)
            .join(
                AnalystRunRow,
                AnalystRunRow.announcement_id == AnnouncementRow.id,
            )
            .where(
                AnnouncementRow.published_at < end,
                AnalystRunRow.is_current.is_(True),
                AnalystRunRow.quality_status == "publishable",
                ~AnalystRunRow.model_version.like("deterministic-metadata%"),
            )
            .order_by(desc(AnnouncementRow.published_at), AnnouncementRow.source_id)
        ).all()

    for published_at in published_values:
        value = published_at
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        local = value.astimezone(LONDON)
        if local.date() > on_or_before:
            continue
        if local.time() < resolved_cutoff:
            return local.date()
    return None
