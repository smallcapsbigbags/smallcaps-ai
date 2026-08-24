from __future__ import annotations

from datetime import date, datetime, timezone

from analyst.models import (
    AnalystNote,
    AnnouncementInput,
    DisclosureAssessment,
    GuidanceEvent,
    ImpactDriver,
    KeyFact,
    QualityFlag,
    QualityReport,
    WhatChanged,
)
from database.db import create_database_engine, create_session_factory, init_database
from database.monitoring import MonitoringSheetQuery, MonitoringSheetRepository
from database.product import ProductRepository
from database.repository import IntelligenceRepository
from product.monitoring import MONITORING_SCHEMA_VERSION, word_count


def announcement(
    source_id: str,
    *,
    published_at: datetime,
    title: str,
    ticker: str = "SPR",
) -> AnnouncementInput:
    return AnnouncementInput(
        source_id=source_id,
        ticker=ticker,
        company="Springfield Properties plc",
        published_at=published_at,
        title=title,
        text=(
            f"Source evidence for {source_id}. Net debt and guidance are explicit "
            "where used."
        ),
        source_url=f"https://example.invalid/{source_id}",
        source_urls=[f"https://example.invalid/{source_id}"],
        evidence_status="complete",
        rns_type="Results & trading",
    )


def note(
    source_id: str,
    *,
    rns_type: str,
    headline: str,
    what_changed: str,
    facts: list[KeyFact] | None = None,
    guidance: list[GuidanceEvent] | None = None,
    colour: str = "green",
    score: int = 3,
    view: str = (
        "Good update. The main point is decision-useful and supported by the RNS."
    ),
) -> AnalystNote:
    level = (
        "low"
        if score == 1
        else "medium"
        if score == 2
        else "critical"
        if score == 5
        else "high"
    )
    return AnalystNote(
        source_id=source_id,
        rns_type=rns_type,
        impact_colour=colour,
        impact_score=score,
        impact_level=level,
        impact_rationale=(
            "The disclosed change is material enough to affect monitoring."
        ),
        impact_drivers=[
            ImpactDriver(
                dimension="balance-sheet" if facts else "operations",
                direction="favourable" if colour == "green" else "adverse",
                significance=max(1, score),
                rationale="The RNS contains the relevant evidence.",
            )
        ],
        headline=headline,
        takeaway="The announcement adds a clear, decision-useful change.",
        key_facts=facts or [],
        what_changed=WhatChanged(
            before="The previous position was recorded in Company Memory.",
            today=what_changed,
            read_through=(
                "The investment implication is explicit without a recommendation."
            ),
            coverage_status="established",
        ),
        analyst_view=view,
        supports_case=["The RNS contains a measurable supporting fact."],
        challenges_case=["The next reporting point still needs verification."],
        guidance_events=guidance or [],
        watch_items=["The next measurable company disclosure."],
        disclosure_assessment=DisclosureAssessment(status="complete"),
        source_references=[f"https://example.invalid/{source_id}"],
        confidence=0.92,
    )


def repositories():
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    init_database(engine)
    factory = create_session_factory(engine)
    return (
        IntelligenceRepository(factory),
        ProductRepository(factory),
        MonitoringSheetRepository(factory),
    )


def seed_monitoring_history():
    intelligence, product, monitoring = repositories()
    prior_at = datetime(2026, 8, 20, 7, 0, tzinfo=timezone.utc)
    current_at = datetime(2026, 8, 21, 7, 0, tzinfo=timezone.utc)

    prior = announcement(
        "spr-results",
        published_at=prior_at,
        title="Final Results",
    )
    prior_note = note(
        "spr-results",
        rns_type="Results & trading",
        headline="Net debt falls to £18.2m",
        what_changed="Net debt fell to £18.2m from £24.0m.",
        facts=[
            KeyFact(
                label="Net debt",
                metric="net debt",
                value="£18.2m",
                previous_value="£24.0m",
                period="FY26 year end",
                as_of_date="31 May 2026",
                currency="GBP",
                value_numeric=18.2,
                basis="reported",
            )
        ],
    )
    intelligence.save_analysis(
        prior,
        prior_note,
        prompt_version="analyst-engine-3.3-scbb-monitoring-sheet",
        model_version="recorded",
        quality_report=QualityReport(status="publishable"),
    )

    long_view = (
        "Useful contract confirmation, but it does not change earnings guidance. "
        "The value is real and the delivery timetable is stated. Margin is not "
        "disclosed, so investors still cannot judge the quality of the revenue. "
        "Cash conversion at the next results remains the key test for the "
        "monitoring sheet."
    )
    current = announcement(
        "spr-contract",
        published_at=current_at,
        title="Contract Award",
    )
    current_note = note(
        "spr-contract",
        rns_type="Contracts",
        headline="£12m contract won; margin remains undisclosed",
        what_changed=(
            "A £12m three-year contract was signed; earnings guidance is maintained."
        ),
        facts=[
            KeyFact(
                label="Contract value",
                metric="contract value",
                value="£12m",
                currency="GBP",
                value_numeric=12.0,
                basis="reported",
            )
        ],
        guidance=[
            GuidanceEvent(
                metric="FY27 expectations",
                period="FY27",
                value="Unchanged",
                status="maintained",
                information_status="reiterated",
            )
        ],
        view=long_view,
    )
    intelligence.save_analysis(
        current,
        current_note,
        prompt_version="legacy-publishable-record",
        model_version="recorded",
        quality_report=QualityReport(status="publishable"),
    )
    product.upsert_price_reaction(
        source_id="spr-contract",
        reaction_session="2026-08-21",
        phase="close",
        previous_close=80.0,
        latest_price=84.0,
        daily_change_pct=5.0,
        currency="GBp",
        source="recorded",
        observed_at=datetime(2026, 8, 21, 16, 40, tzinfo=timezone.utc),
    )
    return intelligence, product, monitoring, long_view


def test_monitoring_row_matches_the_existing_sheet_contract() -> None:
    _intelligence, _product, monitoring, _long_view = seed_monitoring_history()

    page = monitoring.list_rows(
        MonitoringSheetQuery(
            date_from=date(2026, 8, 21),
            date_to=date(2026, 8, 21),
            tickers=("spr.l",),
        )
    )

    assert page.schema_version == MONITORING_SCHEMA_VERSION
    assert page.total == page.count == 1
    row = page.items[0]
    assert row.source_id == "spr-contract"
    assert row.ticker == "SPR"
    assert row.signal == "GREEN"
    assert row.what_changed.startswith("A £12m three-year contract")
    assert row.outlook == "MAINTAINED"
    assert row.market_reaction.label == "+5.0% at close"
    assert row.balance_sheet.status == "carried"
    assert row.balance_sheet.label == "Net debt"
    assert row.balance_sheet.value == "£18.2m"
    assert row.balance_sheet.as_of_date == "31 May 2026"
    assert row.balance_sheet.source_id == "spr-results"
    assert row.impact.score == 3
    assert row.detail_url == "/api/v1/monitoring/spr-contract"
    assert row.original_source_url.endswith("/spr-contract")
    assert word_count(row.ai_view) <= 50


def test_monitoring_detail_preserves_full_research_and_marks_legacy_compaction() -> None:
    _intelligence, _product, monitoring, long_view = seed_monitoring_history()

    detail = monitoring.get_detail("spr-contract")

    assert detail is not None
    assert detail.research.analyst_view == long_view
    assert detail.research.provenance.ai_view_compacted is True
    assert detail.research.provenance.analysis_version.startswith(
        "aim-intelligence-analyst-"
    )
    assert detail.research.evidence[0].label == "Contract value"
    assert detail.research.guidance_events[0].status == "maintained"
    assert detail.research.what_changed.today == detail.what_changed
    assert detail.balance_sheet.source_id == "spr-results"


def test_monitoring_filters_sort_and_pagination_are_deterministic() -> None:
    intelligence, _product, monitoring, _long_view = seed_monitoring_history()
    second = announcement(
        "abc-warning",
        ticker="ABC",
        published_at=datetime(2026, 8, 21, 8, 0, tzinfo=timezone.utc),
        title="Trading Update",
    )
    second_note = note(
        "abc-warning",
        rns_type="Results & trading",
        headline="Profit guidance cut",
        what_changed="FY27 profit guidance was downgraded.",
        guidance=[
            GuidanceEvent(
                metric="FY27 profit",
                period="FY27",
                value="Below previous guidance",
                status="downgraded",
            )
        ],
        colour="red",
        score=4,
        view=(
            "Poor update. The earnings case has weakened and the next cash "
            "disclosure matters."
        ),
    )
    intelligence.save_analysis(
        second,
        second_note,
        prompt_version="analyst-engine-3.3-scbb-monitoring-sheet",
        model_version="recorded",
        quality_report=QualityReport(status="publishable"),
    )

    page = monitoring.list_rows(
        MonitoringSheetQuery(
            date_from=date(2026, 8, 21),
            date_to=date(2026, 8, 21),
            signals=("RED",),
            outlooks=("DOWNGRADED",),
            sort="impact",
            limit=1,
        )
    )
    assert page.total == 1
    assert page.items[0].source_id == "abc-warning"
    assert page.items[0].impact.score == 4

    all_rows = monitoring.list_rows(
        MonitoringSheetQuery(
            date_from=date(2026, 8, 21),
            date_to=date(2026, 8, 21),
            sort="latest",
            limit=1,
            offset=0,
        )
    )
    assert all_rows.total == 2
    assert all_rows.count == 1
    assert all_rows.has_more is True
    assert all_rows.items[0].source_id == "abc-warning"


def test_review_records_remain_outside_the_public_monitoring_api() -> None:
    intelligence, _product, monitoring = repositories()
    item = announcement(
        "spr-review",
        published_at=datetime(2026, 8, 21, 7, 0, tzinfo=timezone.utc),
        title="Trading Update",
    )
    intelligence.save_analysis(
        item,
        note(
            "spr-review",
            rns_type="Results & trading",
            headline="Review required",
            what_changed="A source check is required before publication.",
        ),
        prompt_version="analyst-engine-3.3-scbb-monitoring-sheet",
        model_version="recorded",
        quality_report=QualityReport(
            status="review",
            flags=[
                QualityFlag(
                    code="SOURCE_CHECK",
                    severity="review",
                    message="Owner review required.",
                )
            ],
        ),
    )

    page = monitoring.list_rows(
        MonitoringSheetQuery(
            date_from=date(2026, 8, 21),
            date_to=date(2026, 8, 21),
        )
    )
    assert page.items == []
    assert monitoring.get_detail("spr-review") is None
    assert monitoring.get_detail("spr-review", public_only=False) is not None


def test_monitoring_query_rejects_unsafe_ranges_and_unknown_filters() -> None:
    try:
        MonitoringSheetQuery(
            date_from=date(2025, 1, 1),
            date_to=date(2026, 8, 21),
        )
    except ValueError as exc:
        assert "date range" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("long date range should fail")

    try:
        MonitoringSheetQuery(
            date_from=date(2026, 8, 21),
            date_to=date(2026, 8, 21),
            signals=("BLUE",),  # type: ignore[arg-type]
        )
    except ValueError as exc:
        assert "unsupported signal" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("unknown signal should fail")
