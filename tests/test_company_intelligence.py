from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from analyst.models import (
    AnalystNote,
    DisclosureAssessment,
    GuidanceEvent,
    KeyFact,
    ManagementClaim,
    WhatChanged,
)
from database.company_intelligence import CompanyIntelligenceRepository
from database.db import (
    create_database_engine,
    create_session_factory,
    init_database,
)
from database.repository import IntelligenceRepository
from ingestion.manual import build_manual_announcement
from pipeline import FoundationPipeline

LONDON = ZoneInfo("Europe/London")


def _announcement(source_id: str, day: int, debt: float):
    return build_manual_announcement(
        ticker="SPR",
        company="Springfield Properties plc",
        published_at=datetime(2026, 1, day, 7, 0, tzinfo=LONDON),
        title=f"Trading update {source_id}",
        text=(
            f"Springfield reports net debt of £{debt:.1f}m and maintains FY26 "
            "profit expectations. The land sale is expected to complete by June 2026."
        ),
        source_url=f"https://example.invalid/{source_id}",
        rns_type="Results & trading",
        source_id=source_id,
    )


def _note(source_id: str, debt: float, *, claim_status: str = "open") -> AnalystNote:
    return AnalystNote(
        source_id=source_id,
        rns_type="Results & trading",
        impact_colour="amber",
        impact_score=2,
        impact_level="medium",
        impact_rationale="Debt changed while earnings guidance was maintained.",
        headline=f"Net debt now £{debt:.1f}m; guidance unchanged",
        takeaway=(
            f"Springfield reports net debt of £{debt:.1f}m. Full-year profit "
            "expectations are unchanged."
        ),
        key_facts=[
            KeyFact(
                label="Net debt",
                metric="net debt",
                period="Point in time",
                value=f"£{debt:.1f}m",
                value_numeric=debt,
                unit="million",
                currency="GBP",
                as_of_date=f"2026-01-{source_id[-2:]}",
                basis="reported",
                note=f"Company reported net debt of £{debt:.1f}m.",
            )
        ],
        what_changed=WhatChanged(
            before="Coverage is building.",
            today=f"Net debt is £{debt:.1f}m.",
            read_through="The balance-sheet position changed while guidance did not.",
            coverage_status="building",
        ),
        analyst_view=(
            "The new evidence changes financial risk rather than earnings expectations."
        ),
        guidance_events=[
            GuidanceEvent(
                metric="FY26 adjusted PBT",
                period="FY26",
                value="In line with expectations",
                status="maintained",
                note="No numerical range was disclosed.",
            )
        ],
        management_claims=[
            ManagementClaim(
                claim="The land sale is expected to complete by June 2026.",
                claim_key="spr-land-sale-june-2026",
                metric="land sale completion",
                target_date="June 2026",
                status=claim_status,
                outcome=(
                    "Completed before the target date."
                    if claim_status == "delivered"
                    else ""
                ),
                evidence=f"Trading update {source_id}.",
            )
        ],
        watch_items=["Land sale completion", "Next reported net debt"],
        disclosure_assessment=DisclosureAssessment(
            status="partial",
            missing_items=["Cash available after working-capital commitments"],
        ),
        source_references=[f"https://example.invalid/{source_id}"],
        confidence=0.92,
    )


def test_company_intelligence_builds_from_publishable_point_in_time_records() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    init_database(engine)
    factory = create_session_factory(engine)
    repository = IntelligenceRepository(factory)

    first = _announcement("spr-2026-01-05", 5, 24.0)
    second = _announcement("spr-2026-01-20", 20, 18.2)
    repository.save_analysis(
        first,
        _note(first.source_id, 24.0),
        prompt_version="analyst-engine-3.0-company-memory",
        model_version="fixture",
    )
    repository.save_analysis(
        second,
        _note(second.source_id, 18.2, claim_status="delivered"),
        prompt_version="analyst-engine-3.0-company-memory",
        model_version="fixture",
    )

    intelligence = CompanyIntelligenceRepository(factory).get_company_intelligence("SPR")

    assert intelligence is not None
    assert intelligence["ticker"] == "SPR"
    assert intelligence["announcement_count"] == 2
    assert intelligence["coverage_status"] == "building"

    net_debt = next(
        item for item in intelligence["metric_series"] if item["metric"] == "net debt"
    )
    assert net_debt["latest_value"] == "£18.2m"
    assert net_debt["previous_value"] == "£24.0m"
    assert net_debt["change_direction"] == "down"
    assert net_debt["points"][-1]["source_id"] == second.source_id

    assert intelligence["current_guidance"][0]["source_id"] == second.source_id
    assert intelligence["open_management_claims"] == []
    assert intelligence["resolved_management_claims"][0]["status"] == "delivered"
    assert len(intelligence["disclosure_gaps"]) == 1


class MemoryCapturingEngine:
    model_name = "company-memory-fixture"

    def __init__(self) -> None:
        self.contexts: dict[str, list[dict[str, object]]] = {}

    def analyse(self, announcement, prior_context):
        self.contexts[announcement.source_id] = list(prior_context)
        debt = {
            "spr-day-1": 24.0,
            "spr-day-2": 18.2,
            "spr-day-3": 16.0,
        }[announcement.source_id]
        return _note(announcement.source_id, debt)


def test_pipeline_supplies_memory_snapshot_and_only_earlier_rns_records() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    init_database(engine)
    factory = create_session_factory(engine)
    repository = IntelligenceRepository(factory)
    analyst = MemoryCapturingEngine()
    pipeline = FoundationPipeline(
        repository=repository,
        analyst_engine=analyst,
        prompt_version="analyst-engine-3.0-company-memory",
    )

    announcements = [
        _announcement("spr-day-1", 1, 24.0),
        _announcement("spr-day-2", 2, 18.2),
        _announcement("spr-day-3", 3, 16.0),
    ]
    for announcement in announcements:
        pipeline.process(announcement)

    assert analyst.contexts["spr-day-1"] == []

    second_context = analyst.contexts["spr-day-2"]
    assert second_context[0]["context_type"] == "company_memory_snapshot"
    assert second_context[0]["announcement_count"] == 1
    assert [item["source_id"] for item in second_context[1:]] == ["spr-day-1"]

    third_context = analyst.contexts["spr-day-3"]
    memory = third_context[0]
    assert memory["context_type"] == "company_memory_snapshot"
    assert memory["announcement_count"] == 2
    assert memory["generated_before"].startswith("2026-01-03T07:00:00")
    assert [item["source_id"] for item in third_context[1:]] == [
        "spr-day-1",
        "spr-day-2",
    ]
    net_debt = next(
        item for item in memory["metric_series"] if item["metric"] == "net debt"
    )
    assert net_debt["latest_value"] == "£18.2m"
    assert net_debt["previous_value"] == "£24.0m"
    assert all(
        point["source_id"] != "spr-day-3" for point in net_debt["points"]
    )
