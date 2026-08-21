from datetime import datetime, timezone

from analyst.models import (
    AnalystNote,
    AnnouncementInput,
    DisclosureAssessment,
    ImpactDriver,
    KeyFact,
    WhatChanged,
)
from analyst.quality import assess_analysis_quality


def announcement(**updates):
    values = {
        "source_id": "quality-1",
        "ticker": "ABC",
        "company": "ABC plc",
        "published_at": datetime(2026, 8, 21, 7, 0, tzinfo=timezone.utc),
        "title": "Trading Update",
        "text": "FY expectations are maintained and net debt reduced to £10m.",
        "source_url": "https://example.invalid/rns",
        "source_urls": ["https://example.invalid/rns"],
    }
    values.update(updates)
    return AnnouncementInput(**values)


def note(**updates):
    values = {
        "source_id": "quality-1",
        "rns_type": "Results & trading",
        "impact_colour": "green",
        "impact_score": 3,
        "impact_level": "high",
        "impact_rationale": "Lower net debt reduces financial risk while guidance is unchanged.",
        "impact_drivers": [
            ImpactDriver(
                dimension="balance-sheet",
                direction="favourable",
                significance=3,
                rationale="Net debt reduced to £10m.",
            )
        ],
        "headline": "Guidance maintained; net debt reduced",
        "takeaway": "Earnings guidance is unchanged while the financial position improved.",
        "key_facts": [
            KeyFact(
                label="Net debt",
                metric="net debt",
                value="£10m",
                currency="GBP",
                basis="reported",
            )
        ],
        "what_changed": WhatChanged(
            before="Coverage is building.",
            today="Net debt is £10m and guidance is unchanged.",
            read_through="Financial risk reduced without an earnings change.",
        ),
        "analyst_view": "The balance-sheet improvement is the main new information.",
        "disclosure_assessment": DisclosureAssessment(status="complete"),
        "source_references": ["https://example.invalid/rns"],
        "confidence": 0.9,
    }
    values.update(updates)
    return AnalystNote(**values)


def test_complete_note_is_publishable():
    report = assess_analysis_quality(announcement(), note())
    assert report.status == "publishable"


def test_guardrail_warning_blocks():
    report = assess_analysis_quality(
        announcement(),
        note(source_warnings=["GUARDRAIL: Explicit covenant breach was omitted."]),
    )
    assert report.status == "blocked"


def test_established_coverage_without_context_blocks():
    current = note()
    current = current.model_copy(
        update={
            "what_changed": current.what_changed.model_copy(
                update={"coverage_status": "established"}
            )
        }
    )
    report = assess_analysis_quality(announcement(), current, prior_context=[])
    assert report.status == "blocked"


def test_partial_evidence_requires_review():
    report = assess_analysis_quality(
        announcement(evidence_status="partial"),
        note(),
    )
    assert report.status == "review"


def test_deep_analysis_without_source_reference_requires_review():
    current = note(source_references=[])
    report = assess_analysis_quality(
        announcement(source_url="", source_urls=[]),
        current,
    )
    assert report.status == "review"
    assert any(
        flag.code == "MISSING_SOURCE_REFERENCE" for flag in report.flags
    )
