from datetime import datetime
from zoneinfo import ZoneInfo

from analyst.classification import is_administrative_routine, material_priority
from ingestion.investegate_daily import CatalogueAnnouncement

LONDON = ZoneInfo("Europe/London")


def item(title: str) -> CatalogueAnnouncement:
    return CatalogueAnnouncement(
        source_id="test-" + title.lower().replace(" ", "-"),
        ticker="ABC",
        company="ABC plc",
        published_at=datetime(2026, 8, 21, 7, 0, tzinfo=LONDON),
        title=title,
        source_url="https://example.invalid/rns",
    )


def test_true_administrative_notice_is_routine():
    notice = item("Total Voting Rights")
    assert is_administrative_routine(notice) is True
    assert material_priority(notice) == 5


def test_holdings_notice_is_not_auto_routine():
    notice = item("Holding(s) in Company")
    assert is_administrative_routine(notice) is False
    assert material_priority(notice) == 62


def test_material_trading_notice_has_high_priority():
    notice = item("Trading Update")
    assert is_administrative_routine(notice) is False
    assert material_priority(notice) == 90
