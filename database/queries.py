from __future__ import annotations

from collections.abc import Iterable

from sqlalchemy import select

from database.db import session_scope
from database.models import AnnouncementRow
from database.repository import IntelligenceRepository


def known_source_ids(
    repository: IntelligenceRepository, source_ids: Iterable[str]
) -> set[str]:
    """Return source IDs already persisted, so evidence retrieval is not repeated."""

    ids = {value for value in source_ids if value}
    if not ids:
        return set()

    with session_scope(repository.session_factory) as session:
        return set(
            session.scalars(
                select(AnnouncementRow.source_id).where(
                    AnnouncementRow.source_id.in_(ids)
                )
            ).all()
        )
