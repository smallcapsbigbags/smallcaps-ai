from __future__ import annotations

from collections.abc import Iterable

from sqlalchemy import and_, exists, or_, select

from database.db import session_scope
from database.models import AnalystRunRow, AnnouncementRow
from database.repository import IntelligenceRepository
from database.triage_models import AnnouncementTriageRow


def known_source_ids(
    repository: IntelligenceRepository, source_ids: Iterable[str]
) -> set[str]:
    """Return source IDs that have reached a terminal processing state.

    Pass 6 records every discovered RNS before expensive work begins. A metadata
    shell whose triage level is FULL must therefore *not* count as known until a
    current AnalystRun exists, otherwise blocked/deferred material items could be
    silently skipped forever. ARCHIVE is terminal immediately. LIGHT becomes
    terminal only after exact evidence has been persisted (``evidence_hash``), so
    source/batch/screening failures remain retryable on the next ingestion cycle.
    """

    ids = {value for value in source_ids if value}
    if not ids:
        return set()

    current_run_exists = exists(
        select(AnalystRunRow.id).where(
            AnalystRunRow.announcement_id == AnnouncementRow.id,
            AnalystRunRow.is_current.is_(True),
        )
    )
    terminal_triage_exists = exists(
        select(AnnouncementTriageRow.id).where(
            AnnouncementTriageRow.announcement_id == AnnouncementRow.id,
            AnnouncementTriageRow.escalated.is_(False),
            or_(
                AnnouncementTriageRow.processing_level == "ARCHIVE",
                and_(
                    AnnouncementTriageRow.processing_level == "LIGHT",
                    AnnouncementTriageRow.evidence_hash != "",
                ),
            ),
        )
    )

    with session_scope(repository.session_factory) as session:
        return set(
            session.scalars(
                select(AnnouncementRow.source_id).where(
                    AnnouncementRow.source_id.in_(ids),
                    or_(current_run_exists, terminal_triage_exists),
                )
            ).all()
        )
