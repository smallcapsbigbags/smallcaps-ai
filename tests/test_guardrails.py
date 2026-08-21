from __future__ import annotations

from datetime import datetime, timezone

from analyst.guardrails import apply_analysis_guardrails
from analyst.models import AnalystNote, AnnouncementInput, KeyFact, WhatChanged


def _base_note(source_id: str, *, key_facts: list[KeyFact] | None = None) -> AnalystNote:
    return AnalystNote(
        source_id=source_id,
        rns_type="Results & trading",
        impact_colour="grey",
        impact_score=1,
        impact_level="low",
        impact_rationale="No major change.",
        headline="No major change identified",
        takeaway="The update does not materially change the position.",
        key_facts=key_facts or [],
        what_changed=WhatChanged(
            before="Prior position.",
            today="Current position.",
            read_through="No major change.",
        ),
        analyst_view="The evidence is broadly unchanged.",
    )


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
        impact_rationale="Earnings expectations have been reduced.",
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


def test_calculated_operating_margin_does_not_require_share_denominator() -> None:
    announcement = AnnouncementInput(
        source_id="margin-1",
        ticker="ABC",
        company="ABC plc",
        published_at=datetime(2026, 8, 21, 6, 0, tzinfo=timezone.utc),
        title="Trading update",
        text="Revenue was £42.4m and EBITDA was £4.7m.",
    )
    fact = KeyFact(
        label="EBITDA margin",
        metric="EBITDA margin",
        value="11.1%",
        basis="calculated",
        note="Calculated from £4.7m EBITDA / £42.4m revenue = 11.1%.",
    )

    guarded = apply_analysis_guardrails(
        announcement,
        _base_note("margin-1", key_facts=[fact]),
    )

    assert not any("share/control ratio" in item for item in guarded.source_warnings)


def test_calculated_dilution_still_requires_verified_share_denominator() -> None:
    announcement = AnnouncementInput(
        source_id="dilution-1",
        ticker="ABC",
        company="ABC plc",
        published_at=datetime(2026, 8, 21, 6, 0, tzinfo=timezone.utc),
        title="Placing",
        text="The company issued 20m new shares.",
    )
    fact = KeyFact(
        label="Dilution",
        metric="share dilution",
        value="20%",
        basis="calculated",
        note="20m / 100m = 20%.",
    )

    guarded = apply_analysis_guardrails(
        announcement,
        _base_note("dilution-1", key_facts=[fact]),
    )

    assert any("share/control ratio" in item for item in guarded.source_warnings)
