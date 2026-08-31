from __future__ import annotations

from pathlib import Path

from analyst.models import (
    AnalystNote,
    DisclosureAssessment,
    GuidanceEvent,
    ImpactDriver,
    KeyFact,
    QualityReport,
    WhatChanged,
)
from analyst.monitoring_sheet import (
    balance_sheet_is_carried,
    merge_monitoring_quality,
    monitoring_balance_sheet_fact,
    monitoring_contract_flags,
    monitoring_outlook,
    monitoring_signal,
)
from analyst.version import ANALYSIS_VERSION, DEFAULT_PROMPT_VERSION


def note(**updates) -> AnalystNote:
    values = {
        "source_id": "scbb-pass1",
        "rns_type": "Results & trading",
        "impact_colour": "green",
        "impact_score": 3,
        "impact_level": "high",
        "impact_rationale": (
            "Lower net debt reduces financial risk while earnings guidance is unchanged."
        ),
        "impact_drivers": [
            ImpactDriver(
                dimension="balance-sheet",
                direction="favourable",
                significance=3,
                rationale="Net debt fell from £24.0m to £18.2m.",
            )
        ],
        "headline": "Guidance unchanged; net debt falls 24%",
        "takeaway": (
            "Profit guidance remains £14m and net debt fell to £18.2m. "
            "The earnings case is unchanged, but financial risk has reduced."
        ),
        "key_facts": [
            KeyFact(
                label="Net debt",
                metric="net debt",
                value="£18.2m",
                basis="reported",
                as_of_date="2026-05-31",
                comparator="£24.0m",
                previous_value="£24.0m",
                comparator_type="prior-disclosure",
                comparator_source_id="prior-rns",
            ),
            KeyFact(
                label="Guidance",
                metric="adjusted PBT guidance",
                value="£14m",
                basis="reported",
                information_status="reiterated",
            ),
        ],
        "what_changed": WhatChanged(
            before="Net debt was £24.0m and profit guidance was £14m.",
            today=(
                "Net debt fell £5.8m / 24% to £18.2m; "
                "£14m profit guidance was maintained."
            ),
            read_through=(
                "The earnings case is unchanged, but lower debt reduces financial risk."
            ),
            coverage_status="established",
        ),
        "analyst_view": (
            "Good update. No earnings upgrade, but materially lower debt reduces "
            "balance-sheet risk. Need to see the improvement sustained through "
            "operating cash generation at the finals."
        ),
        "guidance_events": [
            GuidanceEvent(
                metric="adjusted PBT",
                period="FY27",
                value="£14m",
                status="maintained",
                previous_value="£14m",
                previous_source_id="prior-rns",
                information_status="reiterated",
            )
        ],
        "watch_items": ["Cash conversion and net debt at the finals."],
        "disclosure_assessment": DisclosureAssessment(status="complete"),
        "source_references": ["https://example.invalid/rns"],
        "confidence": 0.9,
    }
    values.update(updates)
    return AnalystNote(**values)


def test_scbb_monitoring_contract_is_the_final_prompt() -> None:
    contract = Path("prompts/EDITORIAL_OUTPUT_CONTRACT_V1.md").read_text(
        encoding="utf-8"
    )
    for required in (
        "AI View can be selective; facts cannot be selective.",
        "experienced, sceptical UK small-cap equity analyst",
        "private monitoring sheet for a professional investor",
        "Maximum 50 words.",
        "Do not summarise the announcement again.",
        "What Changed — the most important field",
        "Signal and Impact are independent",
        "Good update.",
        "Broadly as expected.",
        "Need to see cash conversion at the finals.",
        "Carried-forward balance-sheet context",
    ):
        assert required in contract


def test_pass1_version_is_code_locked() -> None:
    assert ANALYSIS_VERSION == "aim-intelligence-analyst-3.4"
    assert DEFAULT_PROMPT_VERSION == "analyst-engine-3.4-facts-no-fluff-routing"


def test_monitoring_signal_and_outlook_are_derived_from_existing_fields() -> None:
    current = note()
    assert monitoring_signal(current) == "GREEN"
    assert monitoring_outlook(current) == "MAINTAINED"

    mixed = note(
        guidance_events=[
            GuidanceEvent(metric="revenue", status="upgraded"),
            GuidanceEvent(metric="margin", status="downgraded"),
        ]
    )
    assert monitoring_outlook(mixed) == "MIXED"


def test_balance_sheet_context_retains_provenance() -> None:
    current = note(
        key_facts=[
            KeyFact(
                label="Net debt",
                metric="net debt",
                value="£24.0m",
                basis="reported",
                as_of_date="2026-03-31",
                information_status="previously-disclosed",
                comparator_source_id="prior-rns",
            )
        ]
    )
    fact = monitoring_balance_sheet_fact(current)
    assert fact is not None
    assert fact.metric == "net debt"
    assert balance_sheet_is_carried(fact)


def test_fifty_word_ai_view_remains_publishable() -> None:
    current = note(
        analyst_view=(
            "Good update. No earnings upgrade, but lower debt reduces balance-sheet "
            "risk and gives management more room to execute. Cash conversion remains "
            "the test at the finals, particularly whether working-capital gains are "
            "sustained rather than reversed."
        )
    )
    assert len(current.analyst_view.split()) <= 50
    report = merge_monitoring_quality(
        QualityReport(status="publishable", flags=[]),
        current,
    )
    assert report.status == "publishable"
    assert not any(flag.severity == "review" for flag in report.flags)


def test_ai_view_over_fifty_words_routes_to_owner_review() -> None:
    current = note(analyst_view=" ".join(["word"] * 51))
    report = merge_monitoring_quality(
        QualityReport(status="publishable", flags=[]),
        current,
    )
    assert report.status == "review"
    assert any(flag.code == "SCBB_AI_VIEW_LENGTH" for flag in report.flags)


def test_summary_style_ai_view_is_flagged_without_forcing_a_rewrite() -> None:
    current = note(
        analyst_view=(
            "The company reported lower net debt and maintained guidance. "
            "Cash conversion remains the next test."
        )
    )
    flags = monitoring_contract_flags(current)
    assert any(flag.code == "SCBB_AI_VIEW_SUMMARY_OPENING" for flag in flags)


def test_what_changed_must_be_a_decision_useful_delta() -> None:
    missing = note(
        what_changed=WhatChanged(
            before="Coverage is building.",
            today="Coverage is building.",
            read_through="The investment implication is unclear.",
        )
    )
    report = merge_monitoring_quality(
        QualityReport(status="publishable", flags=[]),
        missing,
    )
    assert report.status == "review"
    assert any(flag.code == "SCBB_WHAT_CHANGED_MISSING" for flag in report.flags)


def test_balance_sheet_driver_requires_supporting_fact() -> None:
    current = note(
        key_facts=[
            KeyFact(
                label="Guidance",
                metric="adjusted PBT guidance",
                value="£14m",
                basis="reported",
            )
        ]
    )
    report = merge_monitoring_quality(
        QualityReport(status="publishable", flags=[]),
        current,
    )
    assert report.status == "review"
    assert any(flag.code == "SCBB_BALANCE_SHEET_FACT_MISSING" for flag in report.flags)
