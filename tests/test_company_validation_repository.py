from __future__ import annotations

from datetime import datetime, timezone

from analyst.models import AnalystNote, AnnouncementInput, KeyFact, WhatChanged
from database.company_validation import CompanyValidationRepository
from database.db import (
    create_database_engine,
    create_session_factory,
    init_database,
)
from database.repository import IntelligenceRepository


def _save(
    repository: IntelligenceRepository,
    *,
    ticker: str,
    company: str,
    source_id: str,
    month: int,
    day: int,
    rns_type: str,
    value: float,
) -> None:
    announcement = AnnouncementInput(
        source_id=source_id,
        ticker=ticker,
        company=company,
        published_at=datetime(2025, month, day, 7, 0, tzinfo=timezone.utc),
        title=f"{rns_type} {source_id}",
        text=f"The company reports a metric of £{value:.1f}m.",
        source_url=f"https://example.invalid/{source_id}",
        source_urls=[f"https://example.invalid/{source_id}"],
        rns_type=rns_type,
    )
    note = AnalystNote(
        source_id=source_id,
        rns_type=rns_type,
        impact_colour="amber",
        impact_score=2,
        impact_level="medium",
        impact_rationale="The disclosed metric changed.",
        headline=f"Metric now £{value:.1f}m",
        takeaway="The company reported an updated metric.",
        key_facts=[
            KeyFact(
                label="Net debt",
                metric="net debt",
                period="Point in time",
                value=f"£{value:.1f}m",
                value_numeric=value,
                unit="million",
                currency="GBP",
                basis="reported",
                note="Reported by the company.",
            )
        ],
        what_changed=WhatChanged(
            before="Coverage is building.",
            today="The company reported an updated metric.",
            read_through="The balance-sheet evidence changed.",
        ),
        analyst_view="The reported metric is the main new information.",
        source_references=[f"https://example.invalid/{source_id}"],
        confidence=0.9,
    )
    repository.save_analysis(
        announcement,
        note,
        prompt_version="analyst-engine-3.0-company-memory",
        model_version="validation-fixture",
    )


def test_company_validation_repository_ranks_candidates_and_loads_timeline() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    init_database(engine)
    factory = create_session_factory(engine)
    intelligence = IntelligenceRepository(factory)

    _save(
        intelligence,
        ticker="SPR",
        company="Springfield Properties plc",
        source_id="spr-1",
        month=1,
        day=15,
        rns_type="Results & trading",
        value=24.0,
    )
    _save(
        intelligence,
        ticker="SPR",
        company="Springfield Properties plc",
        source_id="spr-2",
        month=5,
        day=20,
        rns_type="Corporate",
        value=1.0,
    )
    _save(
        intelligence,
        ticker="AMCO",
        company="Amcomri Group plc",
        source_id="amco-1",
        month=2,
        day=1,
        rns_type="Results & trading",
        value=2.0,
    )
    _save(
        intelligence,
        ticker="AMCO",
        company="Amcomri Group plc",
        source_id="amco-2",
        month=4,
        day=1,
        rns_type="Acquisition",
        value=2.5,
    )
    _save(
        intelligence,
        ticker="AMCO",
        company="Amcomri Group plc",
        source_id="amco-3",
        month=6,
        day=1,
        rns_type="Results & trading",
        value=3.0,
    )

    repository = CompanyValidationRepository(factory)
    candidates = repository.list_candidates(
        min_announcements=2,
        limit=10,
        preferred_tickers=("SPR",),
    )

    assert [item["ticker"] for item in candidates] == ["SPR", "AMCO"]
    assert candidates[0]["announcement_count"] == 2
    assert candidates[0]["event_type_count"] == 2
    assert candidates[1]["announcement_count"] == 3

    timeline = repository.load_timeline("SPR")
    assert timeline is not None
    assert timeline["company"] == "Springfield Properties plc"
    assert [item["source_id"] for item in timeline["records"]] == [
        "spr-1",
        "spr-2",
    ]
    assert all(item["ticker"] == "SPR" for item in timeline["records"])

    engine.dispose()
