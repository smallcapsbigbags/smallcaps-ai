from __future__ import annotations

from datetime import date, datetime, timezone

from database.daily_editor import DailyEditorRepository
from database.db import create_database_engine, create_session_factory, init_database, session_scope
from database.editorial_calibration import EditorialCalibrationRepository
from database.models import AnalystRunRow, AnnouncementRow, CompanyRow


def _add_full(
    session,
    *,
    company: CompanyRow,
    source_id: str,
    published_at: datetime,
    title: str,
    rns_type: str,
    impact_score: int = 4,
    colour: str = "amber",
) -> None:
    announcement = AnnouncementRow(
        company_id=company.id,
        source_id=source_id,
        published_at=published_at,
        headline=title,
        announcement_type=rns_type,
        source_url=f"https://example.invalid/{source_id}",
        source_urls=[f"https://example.invalid/{source_id}"],
        source_note="test",
        evidence_status="complete",
        raw_text="Decision-useful evidence.",
        categories=[],
    )
    session.add(announcement)
    session.flush()
    session.add(
        AnalystRunRow(
            announcement_id=announcement.id,
            impact_colour=colour,
            impact_score=impact_score,
            impact_level="critical" if impact_score == 5 else "high" if impact_score >= 3 else "medium" if impact_score == 2 else "low",
            impact_rationale="Decision-useful change.",
            impact_drivers=[],
            headline=f"{source_id} analyst verdict",
            takeaway="The investment case changed.",
            new_information=[],
            reiterated_information=[],
            what_changed={
                "before": "Previous position.",
                "today": f"{source_id} changed today.",
                "read_through": "Decision-useful change.",
                "coverage_status": "building",
            },
            analyst_view=f"{source_id} validated analyst view.",
            supports_case=[],
            challenges_case=[],
            watch_items=[],
            disclosure_assessment={"status": "partial"},
            source_references=[f"https://example.invalid/{source_id}"],
            source_warnings=[],
            quality_status="publishable",
            quality_flags=[],
            confidence=0.9,
            prompt_version="analyst-engine-3.3-scbb-monitoring-sheet",
            model_version="recorded",
            analysis_version="aim-intelligence-analyst-3.3",
            is_current=True,
        )
    )


def test_story_links_persist_a_developing_story_across_market_days() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    init_database(engine)
    factory = create_session_factory(engine)

    with session_scope(factory) as session:
        company = CompanyRow(ticker="GAMA", company_name="Gamma plc")
        session.add(company)
        session.flush()
        _add_full(
            session,
            company=company,
            source_id="gama-offer",
            published_at=datetime(2026, 8, 21, 6, 5, tzinfo=timezone.utc),
            title="Possible Offer",
            rns_type="Takeover",
        )
        _add_full(
            session,
            company=company,
            source_id="gama-rule26",
            published_at=datetime(2026, 8, 22, 6, 5, tzinfo=timezone.utc),
            title="Rule 2.6 Deadline",
            rns_type="Takeover",
            impact_score=1,
            colour="grey",
        )
        _add_full(
            session,
            company=company,
            source_id="gama-trading",
            published_at=datetime(2026, 8, 22, 6, 10, tzinfo=timezone.utc),
            title="Trading Update",
            rns_type="Results & trading",
            impact_score=3,
            colour="green",
        )

    calibration = EditorialCalibrationRepository(factory)
    assert calibration.ensure_story_links(date(2026, 8, 21)) == 1
    assert calibration.ensure_story_links(date(2026, 8, 22)) == 2
    links = calibration.links_for_source_ids(
        ["gama-offer", "gama-rule26", "gama-trading"]
    )

    assert links["gama-offer"][0] == links["gama-rule26"][0]
    assert links["gama-offer"][1] == "takeover"
    assert links["gama-trading"][0] != links["gama-offer"][0]
    assert links["gama-trading"][1] == "trading"

    engine.dispose()


def test_owner_override_is_applied_and_becomes_a_calibration_case() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    init_database(engine)
    factory = create_session_factory(engine)

    with session_scope(factory) as session:
        takeover = CompanyRow(ticker="AAA", company_name="AAA plc")
        contract = CompanyRow(ticker="BBB", company_name="BBB plc")
        session.add_all([takeover, contract])
        session.flush()
        _add_full(
            session,
            company=takeover,
            source_id="aaa-offer",
            published_at=datetime(2026, 8, 21, 6, 0, tzinfo=timezone.utc),
            title="Possible Offer",
            rns_type="Takeover",
            impact_score=4,
        )
        _add_full(
            session,
            company=contract,
            source_id="bbb-contract",
            published_at=datetime(2026, 8, 21, 6, 10, tzinfo=timezone.utc),
            title="Contract Award",
            rns_type="Contracts",
            impact_score=4,
            colour="green",
        )

    calibration = EditorialCalibrationRepository(factory)
    calibration.ensure_story_links(date(2026, 8, 21))
    editor = DailyEditorRepository(factory)
    baseline = editor.get_edition(
        date(2026, 8, 21),
        edition_state="morning_note",
        apply_overrides=False,
    )
    assert baseline.lead is not None
    assert baseline.lead.primary_source_id == "aaa-offer"
    assert baseline.also_matters[0].primary_source_id == "bbb-contract"

    snapshot = editor.algorithm_snapshot(
        date(2026, 8, 21),
        source_id="bbb-contract",
        edition_state="morning_note",
    )
    result = calibration.record_override(
        day=date(2026, 8, 21),
        edition_state="morning_note",
        action="lead",
        source_id="bbb-contract",
        reason="Contract is unusually important for this edition.",
        algorithm_score=int(snapshot["algorithm_score"]),
        algorithm_bucket=str(snapshot["algorithm_bucket"]),  # type: ignore[arg-type]
        algorithm_story_key=str(snapshot["story_key"]),
        snapshot=snapshot,
    )

    edited = editor.get_edition(
        date(2026, 8, 21),
        edition_state="morning_note",
    )
    assert edited.lead is not None
    assert edited.lead.primary_source_id == "bbb-contract"
    assert edited.lead.override_actions == ["lead"]
    assert edited.override_count == 1

    cases = calibration.calibration_cases()
    assert len(cases) == 1
    assert cases[0]["case_key"] == result["case_key"]
    assert cases[0]["algorithm_bucket"] == "also_matters"
    assert cases[0]["expected_bucket"] == "lead"
    assert cases[0]["reason"] == "Contract is unusually important for this edition."

    engine.dispose()
