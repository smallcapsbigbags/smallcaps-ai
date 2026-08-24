from datetime import datetime, timezone
from pathlib import Path

from analyst.models import (
    AnalystNote,
    AnnouncementInput,
    DisclosureAssessment,
    ImpactDriver,
    KeyFact,
    WhatChanged,
)
from analyst.quality import assess_analysis_quality
from analyst.version import ANALYSIS_VERSION, DEFAULT_PROMPT_VERSION


def announcement() -> AnnouncementInput:
    return AnnouncementInput(
        source_id="pass4-test",
        ticker="ABC",
        company="ABC plc",
        published_at=datetime(2026, 8, 21, 7, 0, tzinfo=timezone.utc),
        title="Trading Update",
        text="The company maintains guidance and reports net debt of £10m.",
        source_url="https://example.invalid/rns",
        source_urls=["https://example.invalid/rns"],
    )


def note(**updates) -> AnalystNote:
    values = {
        "source_id": "pass4-test",
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
                rationale="Net debt is £10m.",
            )
        ],
        "headline": "Guidance unchanged; net debt falls to £10m",
        "takeaway": (
            "The company maintains earnings guidance and reports net debt of £10m. "
            "Lower debt reduces financial risk without changing the earnings case."
        ),
        "key_facts": [
            KeyFact(label="Net debt", metric="net debt", value="£10m", basis="reported"),
            KeyFact(label="Guidance", metric="guidance", value="Unchanged", basis="reported"),
        ],
        "what_changed": WhatChanged(
            before="Coverage is building.",
            today="Guidance is unchanged and net debt is £10m.",
            read_through="Financial risk has reduced without an earnings upgrade.",
        ),
        "analyst_view": (
            "Balance-sheet risk has reduced, but there is no earnings upgrade. "
            "The next test is whether lower debt is sustained through operating cash generation."
        ),
        "watch_items": ["Next reported net debt and cash conversion."],
        "disclosure_assessment": DisclosureAssessment(status="complete"),
        "source_references": ["https://example.invalid/rns"],
        "confidence": 0.9,
    }
    values.update(updates)
    return AnalystNote(**values)


def test_current_analyst_version_is_code_locked() -> None:
    assert ANALYSIS_VERSION == "aim-intelligence-analyst-3.3"
    assert DEFAULT_PROMPT_VERSION == "analyst-engine-3.3-scbb-monitoring-sheet"


def test_editorial_contract_is_loaded_into_initial_and_review_prompts() -> None:
    source = Path("analyst/analyzer.py").read_text(encoding="utf-8")
    assert "EDITORIAL_OUTPUT_CONTRACT_V1.md" in source
    assert "editorial_prompt" in source
    assert "editorial-output-contract problems" in source
    assert "first three key facts" in source


def test_editorial_contract_locks_required_public_outputs() -> None:
    contract = Path("prompts/EDITORIAL_OUTPUT_CONTRACT_V1.md").read_text(encoding="utf-8")
    for required in (
        "Verdict → Evidence → Smallcaps.ai interpretation → What to watch → Depth",
        "Funding & solvency",
        "normally 6–12 words",
        "two short sentences and no more than about 45 words",
        "first three key facts",
        "normally 1–4 words",
        "one concise sentence, normally no more than about 35 words",
        "Maximum 50 words",
        "Administration imminent; no shareholder return expected",
        "Formal takeover interest emerges; terms remain unknown",
    ):
        assert required in contract


def test_pipeline_applies_canonical_taxonomy_before_quality() -> None:
    source = Path("pipeline.py").read_text(encoding="utf-8")
    taxonomy_pos = source.index("canonical_rns_type")
    guardrail_pos = source.index("guarded_note = apply_analysis_guardrails")
    quality_pos = source.index("quality = assess_analysis_quality")
    monitoring_pos = source.index("quality = merge_monitoring_quality")
    assert taxonomy_pos < guardrail_pos < quality_pos < monitoring_pos


def test_good_pass4_note_remains_publishable() -> None:
    report = assess_analysis_quality(announcement(), note())
    assert report.status == "publishable"
    assert not any(flag.code.startswith("EDITORIAL_") for flag in report.flags)


def test_material_editorial_drift_routes_to_review() -> None:
    long_headline = (
        "This extremely long analyst headline describes an announcement process in far too many words "
        "instead of giving the investor a concise outcome led verdict immediately"
    )
    long_takeaway = " ".join(["word"] * 75) + "."
    report = assess_analysis_quality(
        announcement(),
        note(headline=long_headline, takeaway=long_takeaway),
    )
    assert report.status == "review"
    codes = {flag.code for flag in report.flags}
    assert "EDITORIAL_HEADLINE_LENGTH" in codes
    assert "EDITORIAL_TAKEAWAY_LENGTH" in codes


def test_ambiguous_feed_fact_value_is_flagged_without_blocking() -> None:
    current = note(
        key_facts=[
            KeyFact(
                label="Administration",
                metric="administration status",
                value="Filed",
                basis="reported",
            )
        ]
    )
    report = assess_analysis_quality(announcement(), current)
    assert report.status == "publishable"
    assert any(
        flag.code == "EDITORIAL_AMBIGUOUS_FACT_VALUE" and flag.severity == "info"
        for flag in report.flags
    )
