from __future__ import annotations

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from sqlalchemy import func, select

from analyst.models import (
    AnalystNote,
    DisclosureAssessment,
    ImpactDriver,
    KeyFact,
    ManagementClaim,
    WhatChanged,
)
from database.db import (
    create_database_engine,
    create_session_factory,
    init_database,
)
from database.models import (
    AnalystRunRow,
    AnnouncementRow,
    CompanyRow,
    FactRow,
    ManagementClaimRow,
)
from database.repository import IntelligenceRepository
from ingestion.manual import build_manual_announcement
from pipeline import FoundationPipeline

LONDON = ZoneInfo("Europe/London")


class RecordedIHCAnalystEngine:
    model_name = "recorded-pass-2-fixture"

    def analyse(self, announcement, prior_context):
        assert announcement.ticker == "IHC"
        assert prior_context == []
        return AnalystNote(
            source_id=announcement.source_id,
            rns_type="Remuneration",
            impact_colour="amber",
            impact_score=2,
            impact_level="medium",
            impact_rationale=(
                "The award creates potential dilution, partly offset by "
                "performance-conditioned vesting."
            ),
            impact_drivers=[
                ImpactDriver(
                    dimension="dilution",
                    direction="mixed",
                    significance=2,
                    rationale=(
                        "2,759,141 nil-cost options were awarded, but the "
                        "dilution percentage is not disclosed in the excerpt."
                    ),
                )
            ],
            headline=(
                "Large nil-cost incentive award; shareholder impact depends on vesting"
            ),
            takeaway=(
                "The company granted 2,759,141 nil-cost options, including "
                "1,822,268 to the CEO and CFO. The three-year LTIP element is "
                "performance-conditioned, while FY26 bonus awards vest immediately."
            ),
            key_facts=[
                KeyFact(
                    label="Total options awarded",
                    metric="share options",
                    value="2,759,141",
                    value_numeric=2_759_141,
                    unit="shares",
                    basis="reported",
                    note="Awards are nil-cost options over ordinary shares.",
                    information_status="new",
                ),
                KeyFact(
                    label="CEO and CFO allocation",
                    metric="director option allocation",
                    value="1,822,268",
                    value_numeric=1_822_268,
                    unit="shares",
                    basis="reported",
                    information_status="new",
                ),
                KeyFact(
                    label="LTIP performance period end",
                    metric="LTIP performance period",
                    period="three years ending 31 January 2029",
                    value="31 January 2029",
                    basis="reported",
                    information_status="new",
                ),
            ],
            new_information=[
                "2,759,141 nil-cost options were awarded.",
                "The FY26 bonus awards vest immediately.",
            ],
            what_changed=WhatChanged(
                before=(
                    "Coverage initiated; no prior Smallcaps.ai remuneration "
                    "record is available."
                ),
                today=(
                    "The company issued annual LTIP and FY26 bonus awards as "
                    "nil-cost options, with the LTIP subject to EBITDA and "
                    "cash-conversion conditions."
                ),
                read_through=(
                    "The announcement creates prospective dilution and aligns "
                    "part of the award with operating and cash-conversion "
                    "delivery, but the precise dilution percentage is not "
                    "disclosed in the source excerpt."
                ),
                coverage_status="building",
            ),
            analyst_view=(
                "The absolute award size is meaningful and should be assessed "
                "against issued share capital before drawing a dilution "
                "conclusion. Performance conditions improve alignment for the "
                "LTIP element; immediate vesting of FY26 bonus awards is a "
                "separate remuneration outcome rather than evidence of trading."
            ),
            supports_case=[
                "LTIP vesting is linked to adjusted EBITDA and cash-conversion targets.",
            ],
            challenges_case=[
                "The source excerpt does not quantify the award as a percentage of issued share capital.",
                "A substantial portion was allocated to the CEO and CFO.",
            ],
            management_claims=[
                ManagementClaim(
                    claim=(
                        "LTIP awards will vest on the third anniversary subject "
                        "to minimum adjusted EBITDA and EBITDA-to-operating-"
                        "cashflow conversion targets."
                    ),
                    claim_key="ltip-fy29-performance-vesting",
                    metric="LTIP vesting",
                    target_date="31 January 2029",
                    status="open",
                    evidence=(
                        "Grant of awards under Long-Term Incentive Plan, "
                        "7 August 2026."
                    ),
                )
            ],
            watch_items=[
                "Issued share capital and resulting maximum dilution",
                "The disclosed EBITDA and cash-conversion vesting thresholds",
            ],
            disclosure_assessment=DisclosureAssessment(
                status="partial",
                missing_items=["Issued share capital / maximum dilution"],
            ),
            source_references=[announcement.source_url],
            confidence=0.93,
        )


def test_real_rns_fixture_runs_end_to_end_and_versions_analysis() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    init_database(engine)
    factory = create_session_factory(engine)
    repository = IntelligenceRepository(factory)
    pipeline = FoundationPipeline(
        repository=repository,
        analyst_engine=RecordedIHCAnalystEngine(),
        prompt_version="analyst-engine-2.0",
    )

    text = (
        Path(__file__).parent / "fixtures" / "ihc_ltip_2026.txt"
    ).read_text(encoding="utf-8")
    announcement = build_manual_announcement(
        ticker="IHC",
        company="Inspiration Healthcare Group plc",
        published_at=datetime(2026, 8, 7, 7, 0, tzinfo=LONDON),
        title="Grant of awards under Long-Term Incentive Plan",
        text=text,
        source_url="https://example.invalid/original-rns",
        rns_type="Remuneration",
        source_id="ihc-ltip-2026-08-07",
    )

    first = pipeline.process(announcement)
    second = pipeline.process(announcement)

    assert first.source_id == "ihc-ltip-2026-08-07"
    assert first.quality_status == "publishable"
    assert second.analyst_run_id != first.analyst_run_id

    with factory() as session:
        assert session.scalar(
            select(func.count()).select_from(CompanyRow)
        ) == 1
        assert session.scalar(
            select(func.count()).select_from(AnnouncementRow)
        ) == 1
        assert session.scalar(
            select(func.count()).select_from(AnalystRunRow)
        ) == 2
        assert session.scalar(
            select(func.count())
            .select_from(AnalystRunRow)
            .where(AnalystRunRow.is_current.is_(True))
        ) == 1
        assert session.scalar(
            select(func.count()).select_from(FactRow)
        ) == 6
        assert session.scalar(
            select(func.count()).select_from(ManagementClaimRow)
        ) == 2

    current = repository.get_current_analysis("ihc-ltip-2026-08-07")
    assert current is not None
    assert current["ticker"] == "IHC"
    assert current["impact_colour"] == "amber"
    assert current["impact_level"] == "medium"
    assert current["quality_status"] == "publishable"
    assert current["analysis_version"] == "aim-intelligence-analyst-2.0"
