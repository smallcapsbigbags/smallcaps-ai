from __future__ import annotations

from datetime import datetime, timezone

from analyst.context_selector import select_prior_context
from analyst.models import AnnouncementInput


def test_context_selector_keeps_relevant_history_and_chronology() -> None:
    records = [
        {
            "source_id": f"r{i}",
            "published_at": f"2026-0{min(i + 1, 9)}-01T07:00:00+00:00",
            "rns_type": "Corporate",
            "headline": f"Routine item {i}",
        }
        for i in range(10)
    ]
    records[1].update(
        {
            "rns_type": "Results & trading",
            "headline": "Net debt and cash conversion update",
            "facts": [{"metric": "net debt", "value": "£24m"}],
        }
    )
    announcement = AnnouncementInput(
        source_id="today",
        ticker="SPR",
        company="Springfield Properties",
        published_at=datetime(2026, 8, 21, 7, 0, tzinfo=timezone.utc),
        title="Trading update and net debt guidance",
        text="Net debt update.",
        rns_type="Results & trading",
    )

    selected = select_prior_context(records, [announcement], limit=4)

    assert len(selected) == 4
    assert records[1] in selected
    assert selected[-2:] == records[-2:]
    assert [records.index(item) for item in selected] == sorted(
        records.index(item) for item in selected
    )
