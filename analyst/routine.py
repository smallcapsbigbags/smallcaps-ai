from __future__ import annotations

from analyst.classification import classify_metadata_type
from analyst.models import AnalystNote, AnnouncementInput, WhatChanged


def routine_note(
    announcement: AnnouncementInput,
    *,
    reason: str = "Routine administrative disclosure; no deep AI analysis required.",
) -> AnalystNote:
    """Persist routine notices without spending an OpenAI analysis call."""

    rns_type = classify_metadata_type(announcement)
    return AnalystNote(
        source_id=announcement.source_id,
        rns_type=rns_type,
        impact_colour="grey",
        impact_score=1,
        impact_level="low",
        headline=announcement.title,
        takeaway=(
            "Administrative or regulatory disclosure retained for completeness; "
            "no meaningful investment-case change is identified from the catalogue metadata."
        ),
        what_changed=WhatChanged(
            before="No investment-case comparison required for this routine notice.",
            today=announcement.title,
            read_through="No meaningful directional read-through identified.",
            coverage_status="building",
        ),
        analyst_view=(
            "This notice is retained in the AIM Intelligence history but does not warrant "
            "a deep analyst inference call based on its administrative classification."
        ),
        source_warnings=[reason],
        confidence=0.99,
    )
