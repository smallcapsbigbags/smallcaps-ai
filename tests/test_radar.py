from __future__ import annotations

from datetime import datetime

from database.db import create_database_engine, create_session_factory, init_database
from database.models import CompanyRow
from database.radar import RadarRepository
from product.radar import ContractTerms, RadarObservation, detect_radar_setups


def test_read_small_print_detects_optional_contract_value() -> None:
    observation = RadarObservation(
        source_id="xyz-contract",
        ticker="XYZ",
        company="XYZ plc",
        published_at=datetime.fromisoformat("2026-08-26T07:10:00+01:00"),
        title="£12m Contract Award",
        rns_type="Contracts",
        impact_score=4,
        signal="GREEN",
        source_url="https://example.com/xyz",
        contract=ContractTerms(
            headline_value=12,
            committed_value=4,
            optional_value=8,
            currency="GBP",
            margin_disclosed=False,
        ),
    )
    setups = detect_radar_setups(observation)
    assert [item.setup_type for item in setups] == ["READ_THE_SMALL_PRINT"]
    assert setups[0].setup_score >= 70
    assert any("33%" in item.claim for item in setups[0].evidence)


def test_radar_does_not_manufacture_setup_for_fully_committed_contract() -> None:
    observation = RadarObservation(
        source_id="control-contract",
        ticker="CTL",
        company="Control plc",
        published_at=datetime.fromisoformat("2026-08-26T07:45:00+01:00"),
        title="Contract Award",
        rns_type="Contracts",
        impact_score=3,
        signal="GREEN",
        source_url="https://example.com/control",
        contract=ContractTerms(
            headline_value=5,
            committed_value=5,
            optional_value=0,
            margin_disclosed=True,
        ),
    )
    assert detect_radar_setups(observation) == []


def test_radar_repository_persists_and_updates_setup_identity() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    init_database(engine)
    factory = create_session_factory(engine)
    session = factory()
    try:
        session.add(CompanyRow(ticker="XYZ", company_name="XYZ plc"))
        session.commit()
        setup = detect_radar_setups(
            RadarObservation(
                source_id="xyz-contract-1",
                ticker="XYZ",
                company="XYZ plc",
                published_at=datetime.fromisoformat("2026-08-26T07:10:00+01:00"),
                title="£12m Contract Award",
                contract=ContractTerms(headline_value=12, committed_value=4, optional_value=8),
            )
        )[0]
        repo = RadarRepository(session)
        first = repo.upsert(setup)
        session.commit()
        first_id = first.id

        newer = setup.model_copy(
            update={
                "primary_source_id": "xyz-contract-2",
                "source_ids": ["xyz-contract-2"],
                "last_updated_at": datetime.fromisoformat("2026-08-27T07:10:00+01:00"),
            }
        )
        second = repo.upsert(newer)
        session.commit()

        assert second.id == first_id
        assert second.status == "active"
        assert second.source_ids == ["xyz-contract-1", "xyz-contract-2"]

        newest = setup.model_copy(
            update={
                "primary_source_id": "xyz-contract-3",
                "source_ids": ["xyz-contract-3"],
                "last_updated_at": datetime.fromisoformat("2026-08-28T07:10:00+01:00"),
            }
        )
        third = repo.upsert(newest)
        session.commit()

        assert third.id == first_id
        assert third.status == "active"
        assert third.source_ids == ["xyz-contract-1", "xyz-contract-2", "xyz-contract-3"]
        assert len(repo.active()) == 1
    finally:
        session.close()
