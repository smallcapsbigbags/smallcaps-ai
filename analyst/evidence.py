from __future__ import annotations

from collections.abc import Iterable
from urllib.parse import urlparse

from analyst.models import AnnouncementInput


class EvidenceUnavailableError(RuntimeError):
    """Raised when an announcement does not have enough source evidence to analyse."""


_FALLBACK_MARKERS = (
    "no usable source evidence was returned",
    "regulatory announcement catalogue record:",
)


def normalise_source_url(value: str, *, required: bool = False) -> str:
    clean = (value or "").strip()
    if not clean:
        if required:
            raise ValueError("Source URL is required")
        return ""
    parsed = urlparse(clean)
    valid = parsed.scheme.lower() in {"http", "https"} and bool(parsed.netloc)
    if not valid:
        if required:
            raise ValueError("Source URL must be an absolute http:// or https:// URL")
        return ""
    return clean


def dedupe_source_urls(*groups: object) -> list[str]:
    output: list[str] = []
    seen: set[str] = set()
    for group in groups:
        if isinstance(group, str):
            values: Iterable[object] = [group]
        elif isinstance(group, (list, tuple, set)):
            values = group
        else:
            values = []
        for value in values:
            clean = normalise_source_url(str(value or ""))
            if clean and clean not in seen:
                seen.add(clean)
                output.append(clean)
    return output


def validate_announcement_evidence(announcement: AnnouncementInput, *, min_chars: int = 40) -> None:
    if announcement.evidence_status == "metadata-only":
        raise EvidenceUnavailableError("Metadata-only announcements must use the deterministic routine path")
    if announcement.evidence_status == "unavailable":
        raise EvidenceUnavailableError("Source evidence is unavailable")
    cleaned = " ".join(announcement.text.split())
    if len(cleaned) < max(1, min_chars):
        raise EvidenceUnavailableError(f"Source evidence is too short for analysis ({len(cleaned)} characters)")
    lowered = cleaned.lower()
    if any(marker in lowered for marker in _FALLBACK_MARKERS):
        raise EvidenceUnavailableError("Evidence retrieval returned only a catalogue/headline fallback")
