from datetime import datetime, timezone

import pytest

from ingestion.manual import build_manual_announcement


def test_manual_ingestion_rejects_unsafe_source_url() -> None:
    with pytest.raises(ValueError, match="http"):
        build_manual_announcement(ticker="ABC", company="ABC plc", published_at=datetime(2026, 8, 21, 7, 0, tzinfo=timezone.utc), title="Trading Update", text="Guidance maintained.", source_url="javascript:alert(1)")
