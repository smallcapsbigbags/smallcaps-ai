from __future__ import annotations

from datetime import datetime, timezone

from analyst.models import (
    AnalystNote,
    AnnouncementInput,
    ConceptExplanation,
    DisclosureAssessment,
    KeyFact,
    WhatChanged,
)
from analyst.quality import assess_analysis_quality


def _announcement(text: str) -> AnnouncementInput:
    return AnnouncementInput(
        source_id="phase2-test",
        ticker="ABC",
        company="ABC plc",
        published_at=datetime(2026, 8, 21, 7, 0, tzinfo=timezone.utc),
        title="Corporate Update",
        text=text,
        source_url="https://example.invalid/rns",
        source_urls=["https://example.invalid/rns"],
    )


def _note(*, disclosure: DisclosureAssessment | None = None, key_facts: list[KeyFact] | None = None, analyst_view: str = "The change is useful, but the main financial effect still needs proving.") -> AnalystNote:
    return AnalystNote(
        source_id="phase2-test",
        rns_type="Corporate",
        impact_colour="amber",
        impact_score=2,
        impact_level="medium",
        impact_rationale="The announcement changes ownership mechanics but does not change earnings guidance.",
        headline="Ownership mechanics change; earnings guidance unchanged",
        takeaway="The transaction changes how control could be assessed. It does not by itself change the company's earnings outlook.",
        key_facts=key_facts or [],
        what_changed=WhatChanged(
            before="The existing ownership position applied.",
            today="The proposed transaction changes the ownership position.",
            read_through="Control rules matter here, but the announcement is not itself a takeover.",
        ),
        analyst_view=analyst_view,
        disclosure_assessment=disclosure or DisclosureAssessment(status="complete"),
        source_references=["https://example.invalid/rns"],
        confidence=0.9,
    )


def test_rule_9_requires_plain_english_explanation():
    announcement = _announcement(
        "The Panel has agreed a waiver of the obligations under Rule 9 of the Takeover Code."
    )
    report = assess_analysis_quality(announcement, _note())

    assert report.status == "review"
    assert "UNEXPLAINED_RULE_9" in {flag.code for flag in report.flags}


def test_rule_9_explanation_clears_specific_review_flag():
    announcement = _announcement(
        "The Panel has agreed a waiver of the obligations under Rule 9 of the Takeover Code."
    )
    disclosure = DisclosureAssessment(
        status="complete",
        concept_explanations=[
            ConceptExplanation(
                term="Rule 9",
                plain_english=(
                    "A UK takeover rule that can require a shareholder or group acting "
                    "together to make an offer for the remaining shares when control "
                    "crosses certain thresholds."
                ),
                why_it_matters=(
                    "The transaction could change a major shareholder's level of control; "
                    "the Rule 9 issue does not by itself mean the company is being taken over."
                ),
            )
        ],
    )
    report = assess_analysis_quality(announcement, _note(disclosure=disclosure))

    assert "UNEXPLAINED_RULE_9" not in {flag.code for flag in report.flags}
    assert report.status == "publishable"


def test_calculated_fact_must_show_numeric_inputs():
    announcement = _announcement("The company will issue 20 million new shares.")
    calculated = KeyFact(
        label="Dilution",
        value="20%",
        basis="calculated",
        note="Calculated from the enlarged share capital.",
    )
    report = assess_analysis_quality(announcement, _note(key_facts=[calculated]))

    assert report.status == "review"
    assert "CALCULATION_INPUTS_UNCLEAR" in {flag.code for flag in report.flags}


def test_auditable_calculation_remains_publishable():
    announcement = _announcement(
        "The company will issue 20 million new shares; the enlarged share capital will be 100 million shares."
    )
    calculated = KeyFact(
        label="Dilution",
        value="20%",
        basis="calculated",
        note="20m new shares / 100m enlarged shares = 20%.",
    )
    report = assess_analysis_quality(announcement, _note(key_facts=[calculated]))

    assert "CALCULATION_INPUTS_UNCLEAR" not in {flag.code for flag in report.flags}
    assert report.status == "publishable"


def test_jargon_is_flagged_without_automatically_blocking_publication():
    announcement = _announcement("Trading remains unchanged.")
    report = assess_analysis_quality(
        announcement,
        _note(analyst_view="The incremental read-through improves visibility."),
    )

    jargon_flags = [flag for flag in report.flags if flag.code == "PLAIN_ENGLISH_JARGON"]
    assert jargon_flags
    assert all(flag.severity == "info" for flag in jargon_flags)
    assert report.status == "publishable"
