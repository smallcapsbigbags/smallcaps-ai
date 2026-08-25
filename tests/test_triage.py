from __future__ import annotations

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from analyst.models import AnnouncementInput
from ingestion.investegate_daily import CatalogueAnnouncement
from ingestion.triage import (
    TRIAGE_VERSION,
    TriageContext,
    assess_light,
    extract_light_facts,
    initial_triage,
    parse_numeric_amount,
)
from jobs.run_triage_benchmark import run

LONDON = ZoneInfo("Europe/London")


def item(title: str) -> CatalogueAnnouncement:
    return CatalogueAnnouncement(
        source_id="triage-test",
        ticker="TST",
        company="Triage Test plc",
        published_at=datetime(2026, 8, 25, 7, 0, tzinfo=LONDON),
        title=title,
        source_url="https://example.invalid/triage",
    )


def announcement(title: str, text: str) -> AnnouncementInput:
    value = item(title)
    return AnnouncementInput(
        source_id=value.source_id,
        ticker=value.ticker,
        company=value.company,
        published_at=value.published_at,
        title=title,
        text=text,
        source_url=value.source_url,
        source_urls=[value.source_url],
    )


def test_triage_version_and_fail_safe_unknown_default() -> None:
    assert TRIAGE_VERSION == "newsroom-triage-1.0"
    decision = initial_triage(item("Unusual Corporate Statement"))
    assert decision.processing_level == "LIGHT"
    assert "fails safe" in decision.reason


def test_material_and_routine_metadata_split_before_ai() -> None:
    assert initial_triage(item("Total Voting Rights")).processing_level == "ARCHIVE"
    assert initial_triage(item("Director/PDMR Shareholding")).processing_level == "LIGHT"
    assert initial_triage(item("Trading Update")).processing_level == "FULL"
    assert initial_triage(item("Possible Offer under Rule 2.4")).processing_level == "FULL"


def test_contract_escalation_uses_company_scale() -> None:
    initial = initial_triage(item("Contract Award"))
    small = assess_light(
        announcement("Contract Award", "A £500,000 contract has been awarded."),
        context=TriageContext(latest_revenue_value="£100m"),
        initial=initial,
    )
    material = assess_light(
        announcement("Contract Award", "An £8m contract has been awarded."),
        context=TriageContext(latest_revenue_value="£20m"),
        initial=initial,
    )
    assert small.processing_level == "LIGHT"
    assert material.processing_level == "FULL"
    assert material.escalated is True
    assert "10%" in material.escalation_reason


def test_director_event_escalates_for_senior_management_or_recent_warning() -> None:
    initial = initial_triage(item("Director/PDMR Shareholding"))
    senior = assess_light(
        announcement(
            "Director/PDMR Shareholding",
            "The Chief Executive Officer purchased shares for £150,000.",
        ),
        context=TriageContext(),
        initial=initial,
    )
    after_warning = assess_light(
        announcement(
            "Director/PDMR Shareholding",
            "A director purchased ordinary shares for £20,000.",
        ),
        context=TriageContext(recent_adverse_trading=True),
        initial=initial,
    )
    assert senior.processing_level == "FULL"
    assert after_warning.processing_level == "FULL"


def test_light_fact_extraction_is_deterministic_and_non_generative() -> None:
    facts = extract_light_facts(
        "The company granted 5m options representing 4.2% and a £6.5m maximum value."
    )
    kinds = {fact["kind"] for fact in facts}
    assert {"money", "percentage", "securities"}.issubset(kinds)
    assert parse_numeric_amount("£6.5m") == 6_500_000
    assert parse_numeric_amount("100m shares") == 100_000_000


def test_newsroom_triage_benchmark_passes() -> None:
    result = run(Path("benchmarks/triage_cases.json"))
    assert result["passed"] is True
    assert result["failure_count"] == 0
    assert result["metadata_cases"] >= 19
    assert result["light_cases"] >= 12
    assert result["new_full_analyst_calls"] < result["baseline_full_analyst_calls"]
