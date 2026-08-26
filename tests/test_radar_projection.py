from __future__ import annotations

from datetime import datetime

from analyst.company_memory import CompanyMemorySnapshot
from analyst.models import (
    AnalystNote,
    AnnouncementInput,
    GuidanceEvent,
    ImpactDriver,
    KeyFact,
    WhatChanged,
)
from database.db import create_database_engine, create_session_factory, init_database
from database.models import CompanyRow
from database.radar import RadarRepository
from product.radar import CompanyState, detect_radar_setups
from product.radar_projection import build_radar_observation, company_state_from_note


def _announcement() -> AnnouncementInput:
    return AnnouncementInput(
        source_id="projection-contract",
        ticker="XYZ",
        company="XYZ plc",
        published_at=datetime.fromisoformat("2026-08-26T07:10:00+01:00"),
        title="Contract and Trading Update",
        text="Verified source text for the projection test.",
        source_url="https://example.com/xyz",
        rns_type="Contracts",
    )


def _note() -> AnalystNote:
    return AnalystNote(
        source_id="projection-contract",
        rns_type="Contracts",
        impact_colour="green",
        impact_score=4,
        impact_level="high",
        headline="Contract win with upgraded outlook",
        takeaway="The committed economics matter more than the headline value.",
        key_facts=[
            KeyFact(
                label="Total contract value",
                metric="Contract value",
                value="£12m",
                value_numeric=12,
                currency="GBP",
                basis="reported",
            ),
            KeyFact(
                label="Firm committed value",
                metric="Committed contract value",
                value="£4m",
                value_numeric=4,
                currency="GBP",
                basis="reported",
            ),
            KeyFact(
                label="Optional extensions",
                metric="Optional contract value",
                value="£8m",
                value_numeric=8,
                currency="GBP",
                basis="reported",
            ),
        ],
        what_changed=WhatChanged(
            before="Prior guidance was lower.",
            today="Guidance is upgraded and a contract was awarded.",
            read_through="Earnings improve, but most headline contract value remains optional.",
        ),
        analyst_view="Useful win, but the firm economics are smaller than the headline value.",
        impact_drivers=[
            ImpactDriver(
                dimension="earnings",
                direction="favourable",
                significance=4,
                rationale="Revenue and earnings expectations improve.",
            )
        ],
        guidance_events=[
            GuidanceEvent(
                metric="Adjusted EBITDA",
                period="FY27",
                value="£9m",
                status="upgraded",
                previous_value="£8m",
                previous_source_id="prior-guidance",
            )
        ],
        disclosure_assessment={
            "status": "partial",
            "missing_items": ["Contract margin"],
        },
    )


def test_projection_uses_structured_analyst_fields_not_free_form_guessing() -> None:
    previous = CompanyState(earnings="stable")
    observation = build_radar_observation(
        announcement=_announcement(),
        note=_note(),
        memory=CompanyMemorySnapshot(ticker="XYZ", company="XYZ plc"),
        previous_state=previous,
    )

    assert observation.previous_state.earnings == "stable"
    assert observation.current_state.earnings == "improving"
    assert observation.outlook == "UPGRADED"
    assert observation.contract is not None
    assert observation.contract.headline_value == 12
    assert observation.contract.committed_value == 4
    assert observation.contract.optional_value == 8
    assert observation.contract.margin_disclosed is False
    assert observation.surprises[0].direction == "positive"

    setup_types = [item.setup_type for item in detect_radar_setups(observation)]
    assert "READ_THE_SMALL_PRINT" in setup_types
    assert "EARNINGS_INFLECTION" in setup_types


def test_company_state_carries_forward_untouched_dimensions() -> None:
    previous = CompanyState(
        earnings="stable",
        cash="improving",
        balance_sheet="stable",
        funding="stable",
    )
    current = company_state_from_note(_note(), previous=previous)
    assert current.earnings == "improving"
    assert current.cash == "improving"
    assert current.balance_sheet == "stable"
    assert current.funding == "stable"


def test_company_state_persists_between_radar_observations() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    init_database(engine)
    factory = create_session_factory(engine)
    session = factory()
    try:
        session.add(CompanyRow(ticker="XYZ", company_name="XYZ plc"))
        session.commit()
        repo = RadarRepository(session)
        assert repo.get_state("XYZ") == CompanyState()

        state = CompanyState(earnings="improving", cash="stable")
        repo.upsert_state(
            ticker="XYZ",
            state=state,
            source_id="projection-contract",
            updated_at=datetime.fromisoformat("2026-08-26T07:10:00+01:00"),
        )
        session.commit()

        assert repo.get_state("XYZ") == state
    finally:
        session.close()
