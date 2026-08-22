from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

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
    JobRunRow,
    PriceReactionRow,
)
from database.operations import advisory_job_lock
from jobs.update_prices import JOB_NAME, run_price_job
from market.pricing import DayQuote

LONDON = ZoneInfo("Europe/London")


class _Settings:
    database_url = "sqlite+pysqlite:///:memory:"
    market_data_timeout_seconds = 1
    market_data_enabled = True

    @staticmethod
    def runtime_issues(service: str):
        assert service == "prices"
        return [], []


class _PriceClient:
    source_name = "recorded price fixture"

    def day_quote(self, ticker: str) -> DayQuote:
        assert ticker == "SPR"
        return DayQuote(
            latest=105.0,
            previous_close=100.0,
            change_pct=5.0,
        )


class _FailingPriceClient:
    source_name = "failing price fixture"

    def day_quote(self, ticker: str) -> DayQuote:
        raise RuntimeError("market data unavailable")


def _seed_price_target():
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    init_database(engine)
    factory = create_session_factory(engine)
    published_at = datetime(2026, 8, 21, 9, 0, tzinfo=LONDON)

    with session_scope(factory) as session:
        company = CompanyRow(ticker="SPR", company_name="Springfield Properties plc")
        session.add(company)
        session.flush()
        announcement = AnnouncementRow(
            company_id=company.id,
            source_id="spr-price-target",
            published_at=published_at,
            headline="Trading Update",
            announcement_type="Results & trading",
            source_url="https://example.com/rns/spr-price-target",
            source_urls=["https://example.com/rns/spr-price-target"],
            source_note="",
            evidence_status="complete",
            evidence_retrieved_at=published_at,
            raw_text="A complete regulatory announcement with enough evidence for testing.",
            categories=["Trading update"],
        )
        session.add(announcement)
        session.flush()
        session.add(
            AnalystRunRow(
                announcement_id=announcement.id,
                impact_colour="green",
                impact_score=2,
                impact_level="medium",
                impact_rationale="Trading improved.",
                impact_drivers=[],
                headline="Trading improves",
                takeaway="Trading improved in the period.",
                new_information=["Trading improved."],
                reiterated_information=[],
                what_changed={
                    "before": "Earlier trading was softer.",
                    "today": "Trading improved.",
                    "read_through": "The evidence strengthened.",
                    "coverage_status": "building",
                },
                analyst_view="Today's evidence strengthens the investment case.",
                supports_case=[],
                challenges_case=[],
                watch_items=[],
                disclosure_assessment={"status": "complete"},
                source_references=["https://example.com/rns/spr-price-target"],
                source_warnings=[],
                quality_status="publishable",
                quality_flags=[],
                confidence=0.9,
                prompt_version=DEFAULT_PROMPT_VERSION,
                model_version="recorded-test-model",
                analysis_version=ANALYSIS_VERSION,
                is_current=True,
            )
        )

    return engine, factory


def test_price_job_updates_target_and_is_idempotent() -> None:
    engine, factory = _seed_price_target()
    now = datetime(2026, 8, 21, 12, 0, tzinfo=LONDON)

    first = run_price_job(
        _Settings(),
        engine=engine,
        client=_PriceClient(),
        now_london=now,
    )
    second = run_price_job(
        _Settings(),
        engine=engine,
        client=_PriceClient(),
        now_london=now,
    )

    assert first.status == "success"
    assert first.summary["updated"] == 1
    assert second.status == "success"
    assert second.summary["updated"] == 1

    with session_scope(factory) as session:
        reactions = session.scalars(select(PriceReactionRow)).all()
        jobs = session.scalars(
            select(JobRunRow).where(JobRunRow.job_name == JOB_NAME)
        ).all()
    assert len(reactions) == 1
    assert reactions[0].event_day_return == 5.0
    assert reactions[0].close_price is None
    assert len(jobs) == 2
    assert all(job.status == "success" for job in jobs)


def test_price_job_skips_when_another_worker_holds_the_lock() -> None:
    engine, factory = _seed_price_target()
    now = datetime(2026, 8, 21, 12, 0, tzinfo=LONDON)

    with advisory_job_lock(engine, JOB_NAME) as acquired:
        assert acquired is True
        outcome = run_price_job(
            _Settings(),
            engine=engine,
            client=_PriceClient(),
            now_london=now,
        )

    assert outcome.status == "skipped"
    with session_scope(factory) as session:
        reaction_count = session.scalar(
            select(func.count()).select_from(PriceReactionRow)
        )
        latest_job = session.scalar(
            select(JobRunRow)
            .where(JobRunRow.job_name == JOB_NAME)
            .order_by(JobRunRow.started_at.desc())
        )
    assert reaction_count == 0
    assert latest_job is not None and latest_job.status == "skipped"


def test_price_job_records_failure_without_crashing_ingestion_caller() -> None:
    engine, factory = _seed_price_target()
    now = datetime(2026, 8, 21, 12, 0, tzinfo=LONDON)

    outcome = run_price_job(
        _Settings(),
        engine=engine,
        client=_FailingPriceClient(),
        now_london=now,
        raise_on_failure=False,
    )

    assert outcome.status == "degraded"
    assert outcome.summary["failed"] == 1
    assert any("market data failed" in warning for warning in outcome.warnings)
    with session_scope(factory) as session:
        latest_job = session.scalar(
            select(JobRunRow)
            .where(JobRunRow.job_name == JOB_NAME)
            .order_by(JobRunRow.started_at.desc())
        )
    assert latest_job is not None and latest_job.status == "degraded"
