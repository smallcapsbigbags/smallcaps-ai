from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from analyst.classification import (
    canonical_rns_type,
    classify_metadata_type,
    is_administrative_routine,
    material_priority,
)
from analyst.models import AnnouncementInput
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


def full_item(title: str, text: str) -> AnnouncementInput:
    return AnnouncementInput(
        source_id="full-test",
        ticker="ABC",
        company="ABC plc",
        published_at=datetime(2026, 8, 21, 7, 0, tzinfo=timezone.utc),
        title=title,
        text=text,
        source_url="https://example.invalid/rns",
        source_urls=["https://example.invalid/rns"],
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


def test_generic_funding_update_is_material_but_not_automatically_solvency():
    notice = item("Funding Update")
    assert is_administrative_routine(notice) is False
    assert material_priority(notice) == 90
    assert classify_metadata_type(notice) == "Other"


def test_solvency_notice_outranks_other_material_announcements():
    notice = item("Notice of Intention to Appoint Administrators")
    assert is_administrative_routine(notice) is False
    assert material_priority(notice) == 100
    assert classify_metadata_type(notice) == "Funding & solvency"


def test_funding_and_solvency_requires_distress_not_normal_going_concern_wording():
    normal = full_item(
        "Final Results",
        "The directors have a reasonable expectation that the group has adequate resources to continue in operational existence and therefore adopt the going concern basis.",
    )
    assert classify_metadata_type(normal) == "Results & trading"

    distressed = full_item(
        "Funding Update",
        "The company has insufficient funds to continue as a going concern and has filed a notice of intention to appoint administrators.",
    )
    assert classify_metadata_type(distressed) == "Funding & solvency"
    assert canonical_rns_type(distressed, "Fundraising") == "Funding & solvency"


def test_canonical_taxonomy_normalises_takeover_and_unknown_labels():
    takeover = full_item(
        "Response to press speculation",
        "The company confirms preliminary discussions regarding a possible offer. No offer price has been disclosed.",
    )
    assert canonical_rns_type(takeover, "Possible offer") == "Takeover"
    assert canonical_rns_type(takeover, "Other") == "Takeover"

    unclear = full_item("General Update", "The company provides a general corporate update.")
    assert canonical_rns_type(unclear, "Invented model category") == "Other"
