from datetime import datetime, timezone

import pytest

from analyst.evidence import (
    EvidenceUnavailableError,
    validate_announcement_evidence,
)
from analyst.models import AnnouncementInput


def announcement(**updates):
    values = {
        "source_id": "evidence-1",
        "ticker": "ABC",
        "company": "ABC plc",
        "published_at": datetime(2026, 8, 21, 7, 0, tzinfo=timezone.utc),
        "title": "Trading Update",
        "text": "Revenue was £20m and adjusted EBITDA was £3m for the period.",
    }
    values.update(updates)
    return AnnouncementInput(**values)


def test_unavailable_evidence_is_blocked():
    with pytest.raises(EvidenceUnavailableError):
        validate_announcement_evidence(
            announcement(evidence_status="unavailable")
        )


def test_headline_fallback_is_blocked():
    with pytest.raises(EvidenceUnavailableError):
        validate_announcement_evidence(
            announcement(
                text=(
                    "Regulatory announcement: Trading Update. "
                    "No usable source evidence was returned."
                )
            )
        )


def test_complete_evidence_passes():
    validate_announcement_evidence(announcement(), min_chars=20)
