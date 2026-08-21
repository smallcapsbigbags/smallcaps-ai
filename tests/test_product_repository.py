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
from database.db import (
    create_database_engine,
    create_session_factory,
    init_database,
)
from database.product import ProductRepository
from database.repository import IntelligenceRepository


def make_announcement(source_id: str, ticker: str = "SPR") -> AnnouncementInput:
    return AnnouncementInput(
        source_id=source_id,
        ticker=ticker,
        company="Springfield Properties",
        published_at=datetime(2026, 8, 21, 7, 0, tzinfo=timezone.utc),
        title="Trading Update",
        text=(
            "FY expectations remain unchanged. Net debt reduced from £24.0m "
            "to £18.2m."
        ),
        source_url=f"https://example.invalid/{source_id}",
        source_urls=[f"https://example.invalid/{source_id}"],
        evidence_status="complete",
        evidence_retrieved_at=datetime(
            2026, 8, 21, 7, 2, tzinfo=timezone.utc
        ),
        rns_type="Results & trading",
    )


def make_note(source_id: str) -> AnalystNote:
    return AnalystNote(
        source_id=source_id,
        rns_type="Results & trading",
        impact_colour="green",
        impact_score=3,
        impact_level="high",
        impact_rationale=(
            "Lower net debt reduces financial risk while earnings guidance is unchanged."
        ),
        impact_drivers=[
            ImpactDriver(
                dimension="balance-sheet",
                direction="favourable",
                significance=3,
                rationale="Net debt reduced from £24.0m to £18.2m.",
            )
        ],
        headline="Guidance maintained; net debt reduced",
        takeaway=(
            "The earnings position is unchanged. Faster deleveraging is the "
            "decision-useful development."
        ),
        key_facts=[
            KeyFact(
                label="Net debt",
                metric="net debt",
                value="£18.2m",
                currency="GBP",
                value_numeric=18.2,
                previous_value="£24.0m",
                comparator="Previous company disclosure",
                comparator_type="prior-disclosure",
                comparator_source_id="spr-prior",
                basis="reported",
                information_status="new",
            )
        ],
        new_information=["Net debt reduced to £18.2m."],
        reiterated_information=["FY expectations remain unchanged."],
        what_changed=WhatChanged(
            before="Net debt was £24.0m at the previous update.",
            today="Net debt is £18.2m and FY expectations are maintained.",
            read_through=(
                "Balance-sheet risk has reduced without an earnings upgrade."
            ),
            coverage_status="building",
        ),
        analyst_view=(
            "The balance sheet is the important point. Earnings guidance is unchanged."
        ),
        supports_case=["Lower net debt."],
        challenges_case=["No earnings upgrade."],
        guidance_events=[
            GuidanceEvent(
                metric="FY expectations",
                period="FY27",
                value="Maintained",
                status="maintained",
                information_status="reiterated",
            )
        ],
        watch_items=["Cash conversion at the next results."],
        disclosure_assessment=DisclosureAssessment(status="complete"),
        source_references=[f"https://example.invalid/{source_id}"],
        confidence=0.94,
    )


def repositories():
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    init_database(engine)
    factory = create_session_factory(engine)
    return IntelligenceRepository(factory), ProductRepository(factory)


def test_feed_note_company_history_and_price_are_database_backed() -> None:
    intelligence, product = repositories()
    announcement = make_announcement("spr-update")
    intelligence.save_analysis(
        announcement,
        make_note("spr-update"),
        prompt_version="analyst-engine-2.0",
        model_version="recorded",
        quality_report=QualityReport(status="publishable"),
    )

    feed = product.list_feed(date(2026, 8, 21))
    assert [item["source_id"] for item in feed] == ["spr-update"]
    assert feed[0]["key_facts"][0]["value"] == "£18.2m"
    assert feed[0]["price"] is None

    product.upsert_price_reaction(
        source_id="spr-update",
        reaction_session="2026-08-21",
        phase="intraday",
        previous_close=80.0,
        latest_price=84.0,
        daily_change_pct=5.0,
        currency="GBp",
        source="recorded",
        observed_at=datetime(2026, 8, 21, 12, 0, tzinfo=timezone.utc),
    )
    feed = product.list_feed(date(2026, 8, 21))
    assert feed[0]["price"]["daily_change_pct"] == 5.0
    assert feed[0]["price"]["phase"] == "intraday"

    note = product.get_note("spr-update")
    assert note is not None
    assert note["what_changed"]["before"].startswith("Net debt")
    assert note["guidance_events"][0]["status"] == "maintained"

    history = product.company_history("SPR")
    assert history is not None
    assert history["announcement_count"] == 1
    assert history["announcements"][0]["source_id"] == "spr-update"


def test_review_records_are_excluded_from_public_product() -> None:
    intelligence, product = repositories()
    announcement = make_announcement("spr-review")
    intelligence.save_analysis(
        announcement,
        make_note("spr-review"),
        prompt_version="analyst-engine-2.0",
        model_version="recorded",
        quality_report=QualityReport(
            status="review",
            flags=[
                QualityFlag(
                    code="PARTIAL_EVIDENCE",
                    severity="review",
                    message="Owner source check required.",
                )
            ],
        ),
    )

    assert product.list_feed(date(2026, 8, 21)) == []
    assert product.get_note("spr-review") is None
    internal = product.get_note("spr-review", public_only=False)
    assert internal is not None
    assert internal["quality_status"] == "review"
    history = product.company_history("SPR")
    assert history is not None
    assert history["announcement_count"] == 0
    assert product.list_review_queue()[0]["source_id"] == "spr-review"
