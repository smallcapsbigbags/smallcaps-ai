from datetime import datetime, timezone

import pytest
from sqlalchemy import func, select

from analyst.models import AnalystNote, WhatChanged
from database.db import (
    create_database_engine,
    create_session_factory,
    init_database,
)
from database.models import AnnouncementRow
from database.repository import IntelligenceRepository
from ingestion.manual import build_manual_announcement
from pipeline import AnalysisBlockedError, FoundationPipeline


class OmissiveAnalyst:
    model_name = "omissive-test"

    def analyse(self, announcement, prior_context):
        return AnalystNote(
            source_id=announcement.source_id,
            rns_type="Results & trading",
            impact_colour="red",
            impact_score=5,
            impact_level="critical",
            impact_rationale="Earnings expectations have fallen.",
            headline="Earnings expectations reduced",
            takeaway="Management now expects lower earnings.",
            what_changed=WhatChanged(
                before="Prior expectations stood.",
                today="Earnings expectations were reduced.",
                read_through="The near-term earnings base has reset.",
            ),
            analyst_view="The update resets the earnings outlook.",
            confidence=0.9,
        )


def test_guardrail_failure_blocks_persistence():
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    init_database(engine)
    factory = create_session_factory(engine)
    repository = IntelligenceRepository(factory)
    pipeline = FoundationPipeline(
        repository=repository,
        analyst_engine=OmissiveAnalyst(),
        prompt_version="analyst-engine-2.0",
    )
    announcement = build_manual_announcement(
        ticker="XYZ",
        company="Example plc",
        published_at=datetime(
            2026, 8, 21, 7, 0, tzinfo=timezone.utc
        ),
        title="Trading Update",
        text=(
            "The Board is issuing a formal profit warning and now expects "
            "materially lower earnings."
        ),
        source_id="warning-block-test",
    )

    with pytest.raises(AnalysisBlockedError):
        pipeline.process(announcement)

    with factory() as session:
        assert session.scalar(
            select(func.count()).select_from(AnnouncementRow)
        ) == 0
