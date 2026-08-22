from __future__ import annotations

from datetime import datetime, timezone

from analyst.guardrails import apply_analysis_guardrails
from analyst.models import (
    AnalystNote,
    AnnouncementInput,
    GuidanceEvent,
    KeyFact,
    WhatChanged,
)


def _announcement() -> AnnouncementInput:
    return AnnouncementInput(
        source_id="current-1",
        ticker="ABC",
        company="ABC plc",
        published_at=datetime(2026, 8, 22, 7, 0, tzinfo=timezone.utc),
        title="Trading update",
        text="Net debt is now £18m compared with £24m in the previous update.",
    )


def _note(*, comparator_source_id: str = "", previous_source_id: str = "") -> AnalystNote:
    return AnalystNote(
        source_id="current-1",
        rns_type="Results & trading",
        impact_colour="green",
        impact_score=2,
        impact_level="medium",
        impact_rationale="Net debt fell while guidance was unchanged.",
        headline="Net debt falls to £18m",
        takeaway="Net debt fell to £18m from £24m in the previous update.",
        key_facts=[
            KeyFact(
                label="Net debt",
                metric="net debt",
                period="Point in time",
                value="£18m",
                value_numeric=18.0,
                currency="GBP",
                basis="reported",
                comparator="£24m in the previous update",
                comparator_type="prior-disclosure",
                comparator_source_id=comparator_source_id,
                previous_value="£24m",
            )
        ],
        guidance_events=[
            GuidanceEvent(
                metric="FY26 adjusted PBT",
                period="FY26",
                value="In line with expectations",
                status="reiterated",
                previous_value="In line with expectations",
                previous_source_id=previous_source_id,
            )
        ],
        what_changed=WhatChanged(
            before="Net debt was £24m in the previous update.",
            today="Net debt is £18m.",
            read_through="Financial risk has reduced without an earnings change.",
            coverage_status="building",
        ),
        analyst_view="Today's evidence modestly strengthens the case through lower debt.",
        confidence=0.9,
    )


def _memory_context() -> list[dict[str, object]]:
    return [
        {
            "context_type": "company_memory_snapshot",
            "coverage_status": "building",
            "metric_series": [
                {
                    "metric": "net debt",
                    "points": [
                        {
                            "source_id": "old-1",
                            "published_at": "2026-01-01T07:00:00+00:00",
                            "value": "£24m",
                        }
                    ],
                }
            ],
            "current_guidance": [
                {
                    "source_id": "old-guidance",
                    "metric": "FY26 adjusted PBT",
                }
            ],
        }
    ]


def test_nested_memory_source_ids_are_valid_comparator_provenance() -> None:
    guarded = apply_analysis_guardrails(
        _announcement(),
        _note(
            comparator_source_id="old-1",
            previous_source_id="old-guidance",
        ),
        prior_context=_memory_context(),
    )

    assert not any(
        "not present in current evidence or eligible prior context" in warning
        for warning in guarded.source_warnings
    )


def test_current_rns_can_support_a_repeated_historical_comparator() -> None:
    guarded = apply_analysis_guardrails(
        _announcement(),
        _note(
            comparator_source_id="current-1",
            previous_source_id="current-1",
        ),
        prior_context=_memory_context(),
    )

    assert not any(
        "not present in current evidence or eligible prior context" in warning
        for warning in guarded.source_warnings
    )


def test_unknown_fact_comparator_source_id_is_blocked() -> None:
    guarded = apply_analysis_guardrails(
        _announcement(),
        _note(comparator_source_id="future-or-invented"),
        prior_context=_memory_context(),
    )

    assert any(
        "future-or-invented" in warning
        and "not present in current evidence or eligible prior context" in warning
        for warning in guarded.source_warnings
    )


def test_unknown_guidance_source_id_is_blocked() -> None:
    guarded = apply_analysis_guardrails(
        _announcement(),
        _note(previous_source_id="unknown-guidance"),
        prior_context=_memory_context(),
    )

    assert any(
        "unknown-guidance" in warning
        and "not present in current evidence or eligible prior context" in warning
        for warning in guarded.source_warnings
    )
