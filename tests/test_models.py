from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from analyst.models import (
    AnalystNote,
    AnnouncementInput,
    KeyFact,
    WhatChanged,
)


def test_impact_level_must_match_internal_score() -> None:
    with pytest.raises(ValidationError):
        AnalystNote(
            source_id="x",
            rns_type="Other",
            impact_colour="grey",
            impact_score=1,
            impact_level="critical",
            headline="Routine notice",
            takeaway="No meaningful investment change.",
            what_changed=WhatChanged(
                before="Coverage building.",
                today="Routine notice.",
                read_through="No meaningful directional read-through.",
            ),
            analyst_view="No material change identified.",
        )


def test_calculated_fact_requires_inputs():
    with pytest.raises(ValidationError):
        KeyFact(
            label="Dilution",
            value="20%",
            basis="calculated",
        )


def test_not_disclosed_fact_uses_exact_value():
    with pytest.raises(ValidationError):
        KeyFact(
            label="Contract value",
            value="Unknown",
            basis="not-disclosed",
        )


def test_announcement_timestamp_must_be_timezone_aware():
    with pytest.raises(ValidationError):
        AnnouncementInput(
            source_id="x",
            ticker="ABC",
            company="ABC plc",
            published_at=datetime(2026, 8, 21, 7, 0),
            title="Trading Update",
            text="Revenue was £10m.",
        )

    valid = AnnouncementInput(
        source_id="y",
        ticker="abc.l",
        company="ABC plc",
        published_at=datetime(2026, 8, 21, 7, 0, tzinfo=timezone.utc),
        title="Trading Update",
        text="Revenue was £10m.",
    )
    assert valid.ticker == "ABC"


def test_evidence_timestamp_must_be_timezone_aware():
    with pytest.raises(ValidationError):
        AnnouncementInput(
            source_id="z",
            ticker="ABC",
            company="ABC plc",
            published_at=datetime(
                2026, 8, 21, 7, 0, tzinfo=timezone.utc
            ),
            title="Trading Update",
            text="Revenue was £10m.",
            evidence_retrieved_at=datetime(2026, 8, 21, 7, 1),
        )
