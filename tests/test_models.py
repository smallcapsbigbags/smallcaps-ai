from __future__ import annotations

import pytest
from pydantic import ValidationError

from analyst.models import AnalystNote, WhatChanged


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
