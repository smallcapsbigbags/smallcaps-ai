from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

from analyst.models import (
    AnalystNote,
    AnnouncementInput,
    DisclosureAssessment,
    GuidanceEvent,
    ImpactDriver,
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
from database.product import ProductRepository
from database.repository import IntelligenceRepository
from ingestion.daily_service import DailyAIMIngestionService
from ingestion.investegate_daily import CatalogueAnnouncement
from market.pricing import DayQuote
from market.reactions import DailyPriceReactionService
from pipeline import FoundationPipeline

LONDON = ZoneInfo("Europe/London")
DAY = date(2026, 8, 21)


class _Source:
    deep_batch_size = 5

    def __init__(self) -> None:
        self.prepare_calls = 0
        self.fetch_calls = 0
        self.item = CatalogueAnnouncement(
            source_id="spr-mvp-smoke-2026-08-21",
            ticker="SPR",
            company="Springfield Properties plc",
            published_at=datetime(2026, 8, 21, 7, 0, tzinfo=LONDON),
            title="Trading and Balance Sheet Update",
            source_url="https://example.com/rns/spr-mvp-smoke-2026-08-21",
        )

    def list_announcements(self, day):
        assert day == DAY
        return [self.item], []

    def prepare_documents(self, announcements):
        assert [item.source_id for item in announcements] == [self.item.source_id]
        self.prepare_calls += 1
        return []

    def fetch_document(self, announcement):
        assert announcement.source_id == self.item.source_id
        self.fetch_calls += 1
        return AnnouncementInput(
            source_id=announcement.source_id,
            ticker=announcement.ticker,
            company=announcement.company,
            published_at=announcement.published_at,
            title=announcement.title,
            text=(
                "Springfield said FY27 adjusted profit guidance remains £14m. "
                "Net debt fell to £18.2m from £24.0m and management expects "
                "the land disposal programme to complete by 31 January 2027."
            ),
            source_url=announcement.source_url,
            source_urls=[announcement.source_url],
            evidence_status="complete",
            evidence_retrieved_at=datetime(2026, 8, 21, 7, 5, tzinfo=LONDON),
            rns_type="Results & trading",
            categories=["Trading update"],
        )


class _Analyst:
    model_name = "recorded-mvp-smoke"

    def __init__(self) -> None:
        self.calls = 0

    def analyse(self, announcement, prior_context):
        self.calls += 1
        assert announcement.source_id == "spr-mvp-smoke-2026-08-21"
        assert prior_context == []
        return AnalystNote(
            source_id=announcement.source_id,
            rns_type="Results & trading",
            impact_colour="green",
            impact_score=3,
            impact_level="high",
            impact_rationale=(
                "Net debt fell materially while explicit FY27 profit guidance was maintained."
            ),
            impact_drivers=[
                ImpactDriver(
                    dimension="balance-sheet",
                    direction="favourable",
                    significance=3,
                    rationale="Net debt fell to £18.2m from £24.0m.",
                )
            ],
            headline="Net debt falls while FY27 profit guidance is maintained",
            takeaway=(
                "Springfield maintained £14m FY27 adjusted profit guidance and "
                "reported net debt of £18.2m, down from £24.0m."
            ),
            key_facts=[
                KeyFact(
                    label="FY27 adjusted profit guidance",
                    metric="adjusted profit",
                    period="FY27",
                    value="£14.0m",
                    value_numeric=14.0,
                    unit="million",
                    currency="GBP",
                    basis="reported",
                    information_status="reiterated",
                ),
                KeyFact(
                    label="Net debt",
                    metric="net debt",
                    period="Point in time",
                    value="£18.2m",
                    value_numeric=18.2,
                    unit="million",
                    currency="GBP",
                    basis="reported",
                    comparator="£24.0m",
                    comparator_type="prior-disclosure",
                    previous_value="£24.0m",
                    information_status="new",
                ),
                KeyFact(
                    label="Net debt reduction",
                    metric="net debt change",
                    period="Point in time",
                    value="24.2%",
                    value_numeric=24.2,
                    unit="%",
                    basis="calculated",
                    note="Calculated from £24.0m less £18.2m, divided by £24.0m = 24.2%.",
                    information_status="new",
                ),
            ],
            new_information=["Net debt fell to £18.2m from £24.0m."],
            reiterated_information=["FY27 adjusted profit guidance remains £14.0m."],
            what_changed=WhatChanged(
                before="The earlier disclosed net debt figure was £24.0m.",
                today="Net debt is £18.2m and FY27 profit guidance remains £14.0m.",
                read_through=(
                    "The earnings expectation is unchanged, but balance-sheet risk has reduced."
                ),
                coverage_status="building",
            ),
            analyst_view=(
                "Today's evidence modestly strengthens the investment case because "
                "debt has fallen without a reduction in explicit profit guidance."
            ),
            supports_case=["Net debt fell by £5.8m."],
            challenges_case=["There is no earnings upgrade."],
            guidance_events=[
                GuidanceEvent(
                    metric="adjusted profit",
                    period="FY27",
                    value="£14.0m",
                    status="maintained",
                    information_status="reiterated",
                )
            ],
            management_claims=[
                ManagementClaim(
                    claim="Complete the land disposal programme by 31 January 2027.",
                    claim_key="land-disposals-fy27",
                    metric="land disposals",
                    target_date="31 January 2027",
                    status="open",
                    evidence="Trading and Balance Sheet Update, 21 August 2026.",
                )
            ],
            watch_items=[
                "Completion of the land disposal programme by 31 January 2027."
            ],
            disclosure_assessment=DisclosureAssessment(status="complete"),
            source_references=[announcement.source_url],
            confidence=0.93,
        )


class _PriceClient:
    source_name = "recorded market fixture"

    def day_quote(self, ticker: str) -> DayQuote:
        assert ticker == "SPR"
        return DayQuote(
            latest=94.5,
            previous_close=90.0,
            change_pct=5.0,
        )


def test_complete_mvp_chain_from_discovery_to_company_intelligence() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    init_database(engine)
    factory = create_session_factory(engine)
    intelligence = IntelligenceRepository(factory)
    product = ProductRepository(factory)
    company_intelligence = CompanyIntelligenceRepository(factory)
    source = _Source()
    analyst = _Analyst()
    pipeline = FoundationPipeline(
        repository=intelligence,
        analyst_engine=analyst,
        prompt_version="analyst-engine-3.1-sector-intelligence",
    )
    ingestion = DailyAIMIngestionService(
        source=source,
        repository=intelligence,
        pipeline=pipeline,
    )

    first = ingestion.run(DAY)
    second = ingestion.run(DAY)

    assert first.discovered == 1
    assert first.analysed == 1
    assert first.review_required == 0
    assert first.failed == 0
    assert first.blocked == 0
    assert second.already_known == 1
    assert second.analysed == 0
    assert source.prepare_calls == 1
    assert source.fetch_calls == 1
    assert analyst.calls == 1

    price_result = DailyPriceReactionService(
        repository=product,
        client=_PriceClient(),
    ).run(now_london=datetime(2026, 8, 21, 12, 0, tzinfo=LONDON))
    assert price_result.updated == 1

    feed = product.list_feed(DAY)
    assert len(feed) == 1
    assert feed[0]["source_id"] == source.item.source_id
    assert feed[0]["impact_level"] == "high"
    assert feed[0]["source_url"] == source.item.source_url
    assert feed[0]["price"]["event_day_return"] == 5.0

    note = product.get_note(source.item.source_id)
    assert note is not None
    assert note["quality_status"] == "publishable"
    assert note["what_changed"]["coverage_status"] == "building"
    assert note["source_urls"][0] == source.item.source_url
    assert note["key_facts"][2]["basis"] == "calculated"

    history = product.company_history("SPR")
    assert history is not None
    assert history["announcement_count"] == 1
    assert history["announcements"][0]["source_id"] == source.item.source_id

    snapshot = company_intelligence.get_company_intelligence("SPR")
    assert snapshot is not None
    assert snapshot["announcement_count"] == 1
    assert snapshot["coverage_status"] == "building"
    assert len(snapshot["current_guidance"]) == 1
    assert len(snapshot["open_management_claims"]) == 1
    assert snapshot["recent_impact_history"][0]["source_id"] == source.item.source_id
