from __future__ import annotations

from datetime import datetime, timezone

from analyst.guardrails import apply_analysis_guardrails
from analyst.models import AnalystNote, AnnouncementInput, WhatChanged


def test_explicit_profit_warning_cannot_disappear_from_output() -> None:
    announcement = AnnouncementInput(
        source_id="warn-1",
        ticker="XYZ",
        company="Example plc",
        published_at=datetime(2026, 8, 21, 6, 0, tzinfo=timezone.utc),
        title="Trading update",
        text="The Board is issuing a formal profit warning and now expects lower earnings.",
    )
    note = AnalystNote(
        source_id="warn-1",
        rns_type="Results & trading",
        impact_colour="red",
        impact_score=5,
        impact_level="critical",
        headline="Earnings expectations reduced",
        takeaway="Management now expects lower earnings.",
        what_changed=WhatChanged(
            before="Prior expectations stood.",
            today="Earnings expectations were reduced.",
            read_through="The near-term earnings base has reset.",
        ),
        analyst_view="The update resets the earnings outlook.",
    )

    guarded = apply_analysis_guardrails(announcement, note)

    assert any("formal profit warning" in item for item in guarded.source_warnings)
