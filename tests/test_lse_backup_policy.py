from datetime import date, datetime
from zoneinfo import ZoneInfo

from ingestion.investegate_daily import CatalogueAnnouncement, InvestegateDailyAIMSource
from ingestion.multi_source_daily import MultiSourceDailyAIMSource

LONDON = ZoneInfo("Europe/London")
DAY = date(2026, 8, 24)


def _source() -> MultiSourceDailyAIMSource:
    return MultiSourceDailyAIMSource(
        api_key="test-key",
        deep_model="test-model",
        max_pages=2,
    )


def _item(source_id: str, ticker: str, headline: str, url: str) -> CatalogueAnnouncement:
    return CatalogueAnnouncement(
        source_id=source_id,
        ticker=ticker,
        company=f"{ticker} plc" if not source_id.startswith("aim-lse") else ticker,
        published_at=datetime(2026, 8, 24, 7, 0, tzinfo=LONDON),
        title=headline,
        source_url=url,
    )


def test_unmatched_lse_rows_are_held_out_when_investegate_is_healthy(monkeypatch):
    source = _source()
    primary = _item(
        "aim-primary",
        "AIM1",
        "Trading Update",
        "https://www.investegate.co.uk/announcement/primary",
    )
    broader_lse_row = _item(
        "aim-lse-broad",
        "37QB",
        "Instrument Notice",
        "https://www.lse.co.uk/rns/37QB/instrument-notice.html",
    )

    def fake_investegate(self, day):
        self._urls[primary.source_id] = [primary.source_url]
        return [primary], []

    monkeypatch.setattr(InvestegateDailyAIMSource, "list_announcements", fake_investegate)
    monkeypatch.setattr(
        MultiSourceDailyAIMSource,
        "_list_lse",
        lambda self, day: [broader_lse_row],
    )

    items, warnings = source.list_announcements(DAY)

    assert [item.source_id for item in items] == ["aim-primary"]
    assert all(item.ticker != "37QB" for item in items)
    assert any("LSE-only held out=1" in warning for warning in warnings)
    assert any("Investegate remains the discovery authority" in warning for warning in warnings)
