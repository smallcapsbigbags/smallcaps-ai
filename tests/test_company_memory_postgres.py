from __future__ import annotations

import os
from datetime import datetime, timezone

import pytest

from analyst.models import (
    AnalystNote,
    AnnouncementInput,
    DisclosureAssessment,
    KeyFact,
    WhatChanged,
)
from database.company_intelligence import CompanyIntelligenceRepository
from database.db import (
    create_database_engine,
    create_session_factory,
    init_database,
)
from database.models import Base
from database.repository import IntelligenceRepository


def _announcement(source_id: str, day: int, debt: float) -> AnnouncementInput:
    return AnnouncementInput(
        source_id=source_id,
        ticker="SPR",
        company="Springfield Properties plc",
        published_at=datetime(2026, 8, day, 7, 0, tzinfo=timezone.utc),
        title=f"Trading update {day}",
        text=(
            f"Springfield reports net debt of £{debt:.1f}m and maintains "
            "full-year expectations."
        ),
        source_url="",
        source_urls=[f"https://example.invalid/{source_id}"],
        rns_type="Results & trading",
    )


def _note(source_id: str, debt: float) -> AnalystNote:
    return AnalystNote(
        source_id=source_id,
        rns_type="Results & trading",
        impact_colour="amber",
        impact_score=2,
        impact_level="medium",
        impact_rationale="Debt changed while earnings guidance was unchanged.",
        headline=f"Net debt now £{debt:.1f}m",
        takeaway=f"Net debt is £{debt:.1f}m and guidance is unchanged.",
        key_facts=[
            KeyFact(
                label="Net debt",
                metric="net debt",
                period="Point in time",
                value=f"£{debt:.1f}m",
                value_numeric=debt,
                unit="million",
                currency="GBP",
                basis="reported",
                note=f"Company reported net debt of £{debt:.1f}m.",
            )
        ],
        what_changed=WhatChanged(
            before="Coverage is building.",
            today=f"Net debt is £{debt:.1f}m.",
            read_through="Financial risk changed without an earnings reset.",
        ),
        analyst_view="The balance sheet is the main new information.",
        disclosure_assessment=DisclosureAssessment(status="complete"),
        source_references=[f"https://example.invalid/{source_id}"],
        confidence=0.92,
    )


@pytest.mark.skipif(
    not os.getenv("TEST_POSTGRES_URL"),
    reason="TEST_POSTGRES_URL is not configured",
)
def test_company_memory_round_trips_through_postgres() -> None:
    engine = create_database_engine(os.environ["TEST_POSTGRES_URL"])
    Base.metadata.drop_all(engine)
    init_database(engine)
    factory = create_session_factory(engine)
    repository = IntelligenceRepository(factory)

    first = _announcement("spr-pg-1", 1, 24.0)
    second = _announcement("spr-pg-2", 2, 18.2)
    repository.save_analysis(
        first,
        _note(first.source_id, 24.0),
        prompt_version="analyst-engine-3.0-company-memory",
        model_version="postgres-fixture",
    )
    repository.save_analysis(
        second,
        _note(second.source_id, 18.2),
        prompt_version="analyst-engine-3.0-company-memory",
        model_version="postgres-fixture",
    )

    context = repository.load_prior_context(
        "SPR",
        before=datetime(2026, 8, 3, 7, 0, tzinfo=timezone.utc),
    )
    assert [item["source_id"] for item in context] == ["spr-pg-1", "spr-pg-2"]
    assert context[0]["source_url"] == "https://example.invalid/spr-pg-1"
    assert context[1]["facts"][0]["basis"] == "reported"

    intelligence = CompanyIntelligenceRepository(factory).get_company_intelligence("SPR")
    assert intelligence is not None
    net_debt = next(
        item for item in intelligence["metric_series"] if item["metric"] == "net debt"
    )
    assert net_debt["latest_value"] == "£18.2m"
    assert net_debt["previous_value"] == "£24.0m"

    Base.metadata.drop_all(engine)
    engine.dispose()
