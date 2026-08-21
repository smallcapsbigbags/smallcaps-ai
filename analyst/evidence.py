from __future__ import annotations

from analyst.models import AnnouncementInput


class EvidenceUnavailableError(RuntimeError):
    """Raised when an announcement does not have enough source evidence to analyse."""


_FALLBACK_MARKERS = (
    "no usable source evidence was returned",
    "regulatory announcement catalogue record:",
)


def validate_announcement_evidence(
    announcement: AnnouncementInput,
    *,
    min_chars: int = 40,
) -> None:
    """Block deep analysis when retrieval produced only metadata or a fallback headline."""

    if announcement.evidence_status == "metadata-only":
        raise EvidenceUnavailableError(
            "Metadata-only announcements must use the deterministic routine path"
        )
    if announcement.evidence_status == "unavailable":
        raise EvidenceUnavailableError("Source evidence is unavailable")

    cleaned = " ".join(announcement.text.split())
    if len(cleaned) < max(1, min_chars):
        raise EvidenceUnavailableError(
            f"Source evidence is too short for analysis ({len(cleaned)} characters)"
        )

    lowered = cleaned.lower()
    if any(marker in lowered for marker in _FALLBACK_MARKERS):
        raise EvidenceUnavailableError(
            "Evidence retrieval returned only a catalogue/headline fallback"
        )
