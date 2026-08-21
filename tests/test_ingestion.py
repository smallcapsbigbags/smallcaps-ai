from __future__ import annotations

from datetime import datetime, timezone

from ingestion.manual import build_manual_announcement


def test_manual_ingestion_generates_stable_source_id() -> None:
    kwargs = dict(
        ticker="spr.l",
        company="Springfield Properties",
        published_at=datetime(2026, 8, 21, 7, 0, tzinfo=timezone.utc),
        title="Trading update",
        text="Guidance maintained.",
        source_url="https://example.invalid/rns",
    )
    first = build_manual_announcement(**kwargs)
    second = build_manual_announcement(**kwargs)
    assert first.ticker == "SPR"
    assert first.source_id == second.source_id
