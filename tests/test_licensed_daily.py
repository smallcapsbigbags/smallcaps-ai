from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import pytest

from ingestion.licensed_daily import LicensedDailyAIMSource

DAY = date(2026, 9, 2)


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self):
        return self.payload


def _source() -> LicensedDailyAIMSource:
    return LicensedDailyAIMSource(
        feed_url="https://licensed.example/aim",
        feed_token="secret",
        feed_timeout_seconds=12,
        api_key="test-key",
        deep_model="test-model",
        max_pages=2,
    )


def test_licensed_feed_parses_target_day_and_deduplicates() -> None:
    source = _source()
    captured = {}
    payload = {
        "announcements": [
            {
                "ticker": "SPR.L",
                "company": "Springfield Properties plc",
                "published_at": "2026-09-02T07:00:00+01:00",
                "headline": "Trading Update",
                "source_url": "https://issuer.example/rns/trading-update",
                "categories": ["Trading update"],
            },
            {
                "ticker": "SPR",
                "company": "Springfield Properties plc",
                "published_at": "2026-09-02T07:00:00+01:00",
                "headline": "Trading Update",
                "source_url": "https://issuer.example/rns/trading-update",
            },
            {
                "ticker": "OLD",
                "company": "Old plc",
                "published_at": "2026-09-01T07:00:00+01:00",
                "headline": "Old Update",
                "source_url": "https://issuer.example/rns/old",
            },
        ]
    }

    def fake_get(url, **kwargs):
        captured["url"] = url
        captured.update(kwargs)
        return FakeResponse(payload)

    source.session = SimpleNamespace(get=fake_get)
    items, warnings = source.list_announcements(DAY)

    assert len(items) == 1
    assert items[0].ticker == "SPR"
    assert items[0].company == "Springfield Properties plc"
    assert items[0].source_id.startswith("aim-licensed-")
    assert source._urls[items[0].source_id] == [
        "https://issuer.example/rns/trading-update"
    ]
    assert captured["headers"]["Authorization"] == "Bearer secret"
    assert captured["timeout"] == 12
    assert any("accepted=1" in warning for warning in warnings)


def test_licensed_feed_holds_invalid_rows_out() -> None:
    source = _source()
    source.session = SimpleNamespace(
        get=lambda *args, **kwargs: FakeResponse(
            [
                {
                    "ticker": "",
                    "published_at": "2026-09-02T07:00:00+01:00",
                    "headline": "Bad",
                    "source_url": "https://issuer.example/bad",
                },
                {
                    "ticker": "ABC",
                    "published_at": "2026-09-02T07:00:00+01:00",
                    "headline": "Bad URL",
                    "source_url": "",
                },
            ]
        )
    )

    items, warnings = source.list_announcements(DAY)

    assert items == []
    assert any("invalid=2" in warning for warning in warnings)
    assert any("returned no valid rows" in warning for warning in warnings)


def test_licensed_feed_rejects_insecure_remote_url() -> None:
    with pytest.raises(ValueError):
        LicensedDailyAIMSource(
            feed_url="http://licensed.example/aim",
            api_key="test-key",
            deep_model="test-model",
        )
