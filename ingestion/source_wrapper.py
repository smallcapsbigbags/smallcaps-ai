from __future__ import annotations

from typing import Any

from ingestion.source_provenance import (
    normalise_announcement_provenance,
    provenance_counts,
)


class ProvenanceNormalisingDailySource:
    """Apply deterministic URL provenance discipline to any daily source."""

    def __init__(self, source: Any) -> None:
        self._source = source

    def __getattr__(self, name: str) -> Any:
        return getattr(self._source, name)

    def list_announcements(self, day):
        return self._source.list_announcements(day)

    def prepare_documents(self, announcements):
        return self._source.prepare_documents(announcements)

    def fetch_document(self, announcement):
        return normalise_announcement_provenance(
            self._source.fetch_document(announcement)
        )

    def provenance_counts(self) -> dict[str, int]:
        mapping = getattr(self._source, "_urls", {})
        return provenance_counts(mapping if isinstance(mapping, dict) else {})
