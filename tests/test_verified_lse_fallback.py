from datetime import date, datetime
from zoneinfo import ZoneInfo

from database.db import create_database_engine, create_session_factory, init_database, session_scope
from database.models import AnnouncementRow, CompanyRow
from database.repository import IntelligenceRepository
from ingestion.investegate_daily import CatalogueAnnouncement
from ingestion.multi_source_daily import MultiSourceDailyAIMSource
from ingestion.verified_fallback_daily import VerifiedFallbackDailyAIMSource

LONDON = ZoneInfo("Europe/London")
DAY = date(2026, 8, 24)


def _item(source_id: str, ticker: str) -> CatalogueAnnouncement:
    return CatalogueAnnouncement(
        source_id=source_id,
        ticker=ticker,
        company=ticker,
        published_at=datetime(2026, 8, 24, 7, 0, tzinfo=LONDON),
        title="Trading Update",
        source_url=f"https://www.lse.co.uk/rns/{ticker}/trading-update.html",
    )


def test_lse_fallback_admits_only_tickers_previously_seen_via_non_lse_aim_source(monkeypatch):
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    init_database(engine)
    factory = create_session_factory(engine)
    repository = IntelligenceRepository(factory)

    with session_scope(factory) as session:
        verified = CompanyRow(ticker="AIM1", company_name="Verified AIM plc")
        polluted = CompanyRow(ticker="MAIN1", company_name="Main Market plc")
        session.add_all([verified, polluted])
        session.flush()
        session.add(
            AnnouncementRow(
                company_id=verified.id,
                source_id="aim-investegate-history",
                published_at=datetime(2026, 8, 21, 7, 0, tzinfo=LONDON),
                headline="Previous AIM RNS",
                source_url="https://www.investegate.co.uk/announcement/verified",
                source_urls=["https://www.investegate.co.uk/announcement/verified"],
                raw_text="verified",
            )
        )
        session.add(
            AnnouncementRow(
                company_id=polluted.id,
                source_id="aim-lse-probe-only",
                published_at=datetime(2026, 8, 24, 7, 0, tzinfo=LONDON),
                headline="Probe row",
                source_url="https://www.lse.co.uk/rns/MAIN1/probe.html",
                source_urls=["https://www.lse.co.uk/rns/MAIN1/probe.html"],
                raw_text="probe",
            )
        )

    source = VerifiedFallbackDailyAIMSource(
        repository=repository,
        api_key="test-key",
        deep_model="test-model",
    )
    lse_items = [_item("aim-lse-aim1", "AIM1"), _item("aim-lse-main1", "MAIN1")]
    for item in lse_items:
        source._urls[item.source_id] = [item.source_url]

    monkeypatch.setattr(
        MultiSourceDailyAIMSource,
        "list_announcements",
        lambda self, day: (
            lse_items,
            ["Investegate AIM discovery unavailable; LSE.co.uk RNS catalogue is being used as the fallback."],
        ),
    )

    items, warnings = source.list_announcements(DAY)

    assert [item.ticker for item in items] == ["AIM1"]
    assert "aim-lse-main1" not in source._urls
    assert any("accepted=1" in warning and "held out=1" in warning for warning in warnings)
    engine.dispose()
