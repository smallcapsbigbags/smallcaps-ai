from datetime import date, datetime
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from database.db import create_database_engine, create_session_factory, init_database, session_scope
from database.models import AnnouncementRow, CompanyRow
from database.repository import IntelligenceRepository
from ingestion.investegate_daily import CatalogueAnnouncement, InvestegateDailyAIMSource
from ingestion.multi_source_daily import (
    MultiSourceDailyAIMSource,
    VerifiedEvidenceBatch,
    VerifiedEvidenceItem,
)

LONDON = ZoneInfo("Europe/London")
DAY = date(2026, 8, 24)


def _source(*, repository=None) -> MultiSourceDailyAIMSource:
    return MultiSourceDailyAIMSource(
        repository=repository,
        api_key="test-key",
        deep_model="test-model",
        deep_batch_size=5,
        max_pages=3,
    )


def _item(
    *,
    source_id: str,
    source_url: str,
    company: str = "Example Plc",
    ticker: str = "EXM",
    headline: str = "Trading Update",
) -> CatalogueAnnouncement:
    return CatalogueAnnouncement(
        source_id=source_id,
        ticker=ticker,
        company=company,
        published_at=datetime(2026, 8, 24, 7, 0, tzinfo=LONDON),
        title=headline,
        source_url=source_url,
    )


def test_parse_lse_aim_rows_accepts_only_rns():
    html = """
    <html><body>
      <h1>AIM Regulatory News</h1>
      <div>Monday, 24 August 2026</div>
      <table>
        <tr><th>Time</th><th>Source</th><th>TIDM</th><th>Headline</th></tr>
        <tr><td>7:00 am</td><td>RNS</td><td><a href="/rns/EXM/">EXM</a></td>
            <td><a href="/rns/EXM/trading-update-abc.html">Trading Update</a></td></tr>
        <tr><td>7:01 am</td><td>GNW</td><td>IGN</td>
            <td><a href="/rns/IGN/not-rns.html">Not an RNS</a></td></tr>
      </table>
    </body></html>
    """

    page_date, rows = MultiSourceDailyAIMSource._parse_lse_page(html)

    assert page_date == DAY
    assert len(rows) == 1
    published, ticker, headline, source_url = rows[0]
    assert published.strftime("%Y-%m-%d %H:%M") == "2026-08-24 07:00"
    assert ticker == "EXM"
    assert headline == "Trading Update"
    assert source_url == "https://www.lse.co.uk/rns/EXM/trading-update-abc.html"


def test_catalogues_are_merged_and_investegate_identity_is_retained(monkeypatch):
    source = _source()
    investegate = _item(
        source_id="aim-investegate-1",
        source_url="https://www.investegate.co.uk/announcement/1",
    )
    lse = _item(
        source_id="aim-lse-1",
        source_url="https://www.lse.co.uk/rns/EXM/trading-update-abc.html",
        company="EXM",
    )

    def fake_investegate(self, day):
        assert day == DAY
        self._urls[investegate.source_id] = [investegate.source_url]
        return [investegate], []

    monkeypatch.setattr(InvestegateDailyAIMSource, "list_announcements", fake_investegate)
    monkeypatch.setattr(MultiSourceDailyAIMSource, "_list_lse", lambda self, day: [lse])

    items, warnings = source.list_announcements(DAY)

    assert warnings == []
    assert len(items) == 1
    assert items[0].source_id == "aim-investegate-1"
    assert items[0].company == "Example Plc"
    assert source._urls["aim-investegate-1"] == [
        "https://www.investegate.co.uk/announcement/1",
        "https://www.lse.co.uk/rns/EXM/trading-update-abc.html",
    ]


def test_lse_is_used_when_investegate_is_unavailable(monkeypatch):
    source = _source()
    lse = _item(
        source_id="aim-lse-fallback",
        source_url="https://www.lse.co.uk/rns/EXM/trading-update-abc.html",
        company="EXM",
    )

    def fail_investegate(self, day):
        raise RuntimeError("catalogue unavailable")

    monkeypatch.setattr(InvestegateDailyAIMSource, "list_announcements", fail_investegate)
    monkeypatch.setattr(MultiSourceDailyAIMSource, "_list_lse", lambda self, day: [lse])

    items, warnings = source.list_announcements(DAY)

    assert [item.source_id for item in items] == ["aim-lse-fallback"]
    assert any("LSE.co.uk RNS catalogue is being used as the fallback" in warning for warning in warnings)


def test_existing_database_identity_is_reused_for_later_catalogue_alias():
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    init_database(engine)
    factory = create_session_factory(engine)
    repository = IntelligenceRepository(factory)

    with session_scope(factory) as session:
        company = CompanyRow(ticker="EXM", company_name="Example Plc")
        session.add(company)
        session.flush()
        session.add(
            AnnouncementRow(
                company_id=company.id,
                source_id="aim-original-id",
                published_at=datetime(2026, 8, 24, 7, 0, tzinfo=LONDON),
                headline="Trading Update",
                source_url="https://www.investegate.co.uk/announcement/original",
                source_urls=["https://www.investegate.co.uk/announcement/original"],
                raw_text="Existing announcement text",
            )
        )

    source = _source(repository=repository)
    alias = _item(
        source_id="aim-lse-new-alias",
        source_url="https://www.lse.co.uk/rns/EXM/trading-update-abc.html",
        company="EXM",
    )
    source._urls[alias.source_id] = [alias.source_url]

    resolved = source._reuse_existing_source_ids([alias])

    assert resolved[0].source_id == "aim-original-id"
    assert source._urls["aim-original-id"] == [alias.source_url]
    assert "aim-lse-new-alias" not in source._urls
    engine.dispose()


def test_evidence_retrieval_explicitly_prioritises_fca_nsm_and_resolves_company():
    source = _source()
    item = _item(
        source_id="aim-lse-material",
        source_url="https://www.lse.co.uk/rns/EXM/trading-update-abc.html",
        company="EXM",
    )
    source._urls[item.source_id] = [item.source_url]
    captured = {}

    class FakeResponses:
        def parse(self, **kwargs):
            captured.update(kwargs)
            return SimpleNamespace(
                output_parsed=VerifiedEvidenceBatch(
                    records=[
                        VerifiedEvidenceItem(
                            source_id=item.source_id,
                            company="Example Holdings plc",
                            evidence="Example Holdings plc reported revenue of £10m and maintained guidance.",
                            source_urls=[
                                "https://data.fca.org.uk/example-filing",
                                item.source_url,
                            ],
                        )
                    ]
                )
            )

    source.client = SimpleNamespace(responses=FakeResponses())

    source.prepare_documents([item])
    announcement = source.fetch_document(item)

    assert "FCA National Storage Mechanism" in captured["input"]
    assert source.fca_nsm_url in captured["input"]
    assert "Issuer investor-relations" in captured["input"]
    assert announcement.company == "Example Holdings plc"
    assert announcement.source_urls[0] == "https://data.fca.org.uk/example-filing"
