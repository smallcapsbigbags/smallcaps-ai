from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select

from analyst.version import ANALYSIS_VERSION, DEFAULT_PROMPT_VERSION
from database.db import (
    create_database_engine,
    create_session_factory,
    init_database,
    session_scope,
)
from database.models import (
    AnalystRunRow,
    AnnouncementRow,
    CompanyRow,
    FactRow,
    JobRunRow,
    PriceReactionRow,
)
from database.production_audit import run_production_audit


def _seed_healthy_database(*, include_price: bool = True):
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    init_database(engine)
    factory = create_session_factory(engine)
    now = datetime(2026, 8, 22, 17, 0, tzinfo=timezone.utc)

    with session_scope(factory) as session:
        company = CompanyRow(ticker="SPR", company_name="Springfield Properties plc")
        session.add(company)
        session.flush()

        announcement = AnnouncementRow(
            company_id=company.id,
            source_id="spr-production-audit",
            published_at=now - timedelta(hours=4),
            headline="Trading Update",
            announcement_type="Results & trading",
            source_url="https://example.com/rns/spr-production-audit",
            source_urls=["https://example.com/rns/spr-production-audit"],
            source_note="",
            evidence_status="complete",
            evidence_retrieved_at=now - timedelta(hours=3),
            raw_text=(
                "Springfield reported revenue, margin and net cash figures in a "
                "full regulatory announcement used for the production audit."
            ),
            categories=["Trading update"],
        )
        session.add(announcement)
        session.flush()

        run = AnalystRunRow(
            announcement_id=announcement.id,
            impact_colour="green",
            impact_score=2,
            impact_level="medium",
            impact_rationale="Trading improved while the balance sheet remained sound.",
            impact_drivers=[],
            headline="Trading improves with net cash retained",
            takeaway="The company reported better trading and retained net cash.",
            new_information=["Trading improved."],
            reiterated_information=[],
            what_changed={
                "before": "Earlier trading was softer.",
                "today": "Trading improved.",
                "read_through": "The investment case strengthened modestly.",
                "coverage_status": "building",
            },
            analyst_view="Today's evidence modestly strengthens the investment case.",
            supports_case=["Net cash was retained."],
            challenges_case=[],
            watch_items=["Next margin update"],
            disclosure_assessment={"status": "complete", "missing_items": []},
            source_references=["https://example.com/rns/spr-production-audit"],
            source_warnings=[],
            quality_status="publishable",
            quality_flags=[],
            confidence=0.9,
            prompt_version=DEFAULT_PROMPT_VERSION,
            model_version="recorded-test-model",
            analysis_version=ANALYSIS_VERSION,
            is_current=True,
        )
        session.add(run)
        session.flush()

        session.add(
            FactRow(
                company_id=company.id,
                announcement_id=announcement.id,
                analyst_run_id=run.id,
                ordinal=0,
                label="Net cash",
                metric="net cash",
                period="Point in time",
                value="£1.0m",
                unit="million",
                currency="GBP",
                basis="reported",
                note="",
                comparator="",
                comparator_type="none",
                comparator_source_id="",
                previous_value="",
                information_status="new",
            )
        )
        if include_price:
            session.add(
                PriceReactionRow(
                    announcement_id=announcement.id,
                    reaction_session="2026-08-22",
                    previous_close=90.0,
                    latest_price=94.5,
                    close_price=94.5,
                    event_day_return=5.0,
                    currency="GBp",
                    source="test",
                    observed_at=now,
                )
            )

        session.add_all(
            [
                JobRunRow(
                    job_name="daily-aim-ingestion",
                    run_key="2026-08-22",
                    status="success",
                    started_at=now - timedelta(hours=2),
                    finished_at=now - timedelta(hours=1, minutes=55),
                    summary={"discovered": 4, "analysed": 1},
                    warnings=[],
                    error_text="",
                ),
                JobRunRow(
                    job_name="daily-price-reactions",
                    run_key="2026-08-22",
                    status="success",
                    started_at=now - timedelta(hours=1),
                    finished_at=now - timedelta(minutes=55),
                    summary={"updated": 1},
                    warnings=[],
                    error_text="",
                ),
            ]
        )

    return engine, factory, now


def _check_map(report):
    return {check.code: check for check in report.checks}


def test_healthy_operational_record_passes_and_write_probe_rolls_back() -> None:
    engine, factory, now = _seed_healthy_database()

    report = run_production_audit(
        engine,
        factory,
        service="web",
        market_data_enabled=True,
        strict_production=False,
        now=now,
    )

    checks = _check_map(report)
    assert report.passed is True
    assert report.counts["current_publishable"] == 1
    assert report.version_counts[ANALYSIS_VERSION] == 1
    assert checks["DATABASE_WRITE_ROUNDTRIP"].status == "pass"
    assert checks["PUBLIC_SOURCE_LINKS"].status == "pass"
    assert checks["LATEST_INGESTION_JOB"].status == "pass"
    assert checks["MARKET_DATA_OPERATION"].status == "pass"

    with session_scope(factory) as session:
        probe_count = session.scalar(
            select(func.count())
            .select_from(JobRunRow)
            .where(JobRunRow.job_name == "production-audit-write-probe")
        )
    assert probe_count == 0


def test_missing_public_source_link_is_a_launch_failure() -> None:
    engine, factory, now = _seed_healthy_database()
    with session_scope(factory) as session:
        announcement = session.scalar(select(AnnouncementRow))
        run = session.scalar(select(AnalystRunRow))
        assert announcement is not None and run is not None
        announcement.source_url = ""
        announcement.source_urls = []
        run.source_references = []

    report = run_production_audit(
        engine,
        factory,
        service="web",
        market_data_enabled=True,
        strict_production=False,
        now=now,
    )

    assert report.passed is False
    assert _check_map(report)["PUBLIC_SOURCE_LINKS"].status == "fail"


def test_unavailable_evidence_cannot_be_public() -> None:
    engine, factory, now = _seed_healthy_database()
    with session_scope(factory) as session:
        announcement = session.scalar(select(AnnouncementRow))
        assert announcement is not None
        announcement.evidence_status = "unavailable"

    report = run_production_audit(
        engine,
        factory,
        service="web",
        market_data_enabled=True,
        strict_production=False,
        now=now,
    )

    assert report.passed is False
    assert _check_map(report)["NO_UNAVAILABLE_PUBLIC_EVIDENCE"].status == "fail"


def test_stuck_job_is_a_launch_failure() -> None:
    engine, factory, now = _seed_healthy_database()
    with session_scope(factory) as session:
        session.add(
            JobRunRow(
                job_name="daily-aim-ingestion",
                run_key="stuck",
                status="running",
                started_at=now - timedelta(hours=4),
                summary={},
                warnings=[],
                error_text="",
            )
        )

    report = run_production_audit(
        engine,
        factory,
        service="ingestion",
        market_data_enabled=True,
        strict_production=False,
        now=now,
    )

    assert report.passed is False
    assert _check_map(report)["NO_STUCK_JOBS"].status == "fail"


def test_missing_price_history_warns_without_breaking_the_core_feed() -> None:
    engine, factory, now = _seed_healthy_database(include_price=False)

    report = run_production_audit(
        engine,
        factory,
        service="web",
        market_data_enabled=True,
        strict_production=False,
        now=now,
    )

    assert report.passed is True
    assert _check_map(report)["PRICE_REACTION_DATA"].status == "warning"
