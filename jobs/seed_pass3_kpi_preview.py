from __future__ import annotations

import os
from datetime import datetime, timezone

from analyst.models import (
    AnalystNote,
    AnnouncementInput,
    DisclosureAssessment,
    KeyFact,
    WhatChanged,
)
from database.db import create_database_engine, create_session_factory, init_database
from database.repository import IntelligenceRepository

PROMPT_VERSION = "analyst-engine-3.1-sector-intelligence"
MODEL_VERSION = "deterministic-pass3-kpi-preview"


def _announcement(
    *,
    source_id: str,
    published_at: datetime,
    title: str,
    text: str,
) -> AnnouncementInput:
    source_url = f"https://example.com/rns/{source_id}"
    return AnnouncementInput(
        source_id=source_id,
        ticker="KPI",
        company="KPI Integrity plc",
        published_at=published_at,
        title=title,
        text=text,
        source_url=source_url,
        source_urls=[source_url],
        evidence_status="complete",
        evidence_retrieved_at=published_at,
        rns_type="Results & trading",
    )


def _note(
    announcement: AnnouncementInput,
    *,
    metric: str,
    label: str,
    period: str,
    value: str,
    value_numeric: float,
    unit: str,
    before: str,
) -> AnalystNote:
    return AnalystNote(
        source_id=announcement.source_id,
        rns_type="Results & trading",
        impact_colour="grey",
        impact_score=1,
        impact_level="low",
        impact_rationale="Deterministic KPI-history fixture for the Company repository.",
        headline=f"{period} revenue reported at {value}",
        takeaway=f"KPI Integrity reported {period} revenue of {value}.",
        key_facts=[
            KeyFact(
                label=label,
                metric=metric,
                period=period,
                value=value,
                value_numeric=value_numeric,
                unit=unit,
                currency="GBP",
                basis="reported",
                note=f"Company reported {period} revenue of {value}.",
            )
        ],
        new_information=[f"{period} revenue was {value}."],
        reiterated_information=[],
        what_changed=WhatChanged(
            before=before,
            today=f"{period} revenue is {value}.",
            read_through="The disclosure extends the reported revenue history.",
        ),
        analyst_view="This fixture exists only to validate like-for-like KPI history.",
        supports_case=[],
        challenges_case=[],
        watch_items=["The next full-year revenue disclosure."],
        disclosure_assessment=DisclosureAssessment(status="complete"),
        source_references=announcement.source_urls,
        confidence=0.99,
    )


def seed(database_url: str) -> None:
    engine = create_database_engine(database_url)
    init_database(engine)
    repository = IntelligenceRepository(create_session_factory(engine))

    specifications = [
        {
            "source_id": "kpi-fy23-results",
            "published_at": datetime(2024, 3, 15, 7, 0, tzinfo=timezone.utc),
            "title": "Final Results FY23",
            "text": "FY23 turnover was £20.0m.",
            "metric": "turnover",
            "label": "FY23 turnover",
            "period": "FY23",
            "value": "£20.0m",
            "value_numeric": 20.0,
            "unit": "million",
            "before": "Coverage begins with this full-year result.",
        },
        {
            "source_id": "kpi-h1-fy24-results",
            "published_at": datetime(2024, 9, 10, 7, 0, tzinfo=timezone.utc),
            "title": "Interim Results H1 FY24",
            "text": "H1 FY24 revenue was £9.5m.",
            "metric": "revenue",
            "label": "H1 FY24 revenue",
            "period": "H1 FY24",
            "value": "£9.5m",
            "value_numeric": 9.5,
            "unit": "million",
            "before": "FY23 turnover was £20.0m, but the periods are not comparable.",
        },
        {
            "source_id": "kpi-fy24-results",
            "published_at": datetime(2025, 3, 17, 7, 0, tzinfo=timezone.utc),
            "title": "Final Results FY24",
            "text": "FY24 group revenue was £24.0m.",
            "metric": "group revenue",
            "label": "FY24 group revenue",
            "period": "FY24",
            "value": "£24.0m",
            "value_numeric": 24.0,
            "unit": "million",
            "before": "FY23 turnover was £20.0m.",
        },
        {
            "source_id": "kpi-fy25-results",
            "published_at": datetime(2026, 3, 16, 7, 0, tzinfo=timezone.utc),
            "title": "Final Results FY25",
            "text": "FY25 revenue was £28,500k.",
            "metric": "revenue",
            "label": "FY25 revenue",
            "period": "FY25",
            "value": "£28,500k",
            "value_numeric": 28_500.0,
            "unit": "thousand",
            "before": "FY24 group revenue was £24.0m.",
        },
    ]

    for specification in specifications:
        announcement = _announcement(
            source_id=str(specification["source_id"]),
            published_at=specification["published_at"],  # type: ignore[arg-type]
            title=str(specification["title"]),
            text=str(specification["text"]),
        )
        repository.save_analysis(
            announcement,
            _note(
                announcement,
                metric=str(specification["metric"]),
                label=str(specification["label"]),
                period=str(specification["period"]),
                value=str(specification["value"]),
                value_numeric=float(specification["value_numeric"]),
                unit=str(specification["unit"]),
                before=str(specification["before"]),
            ),
            prompt_version=PROMPT_VERSION,
            model_version=MODEL_VERSION,
        )

    engine.dispose()


if __name__ == "__main__":
    seed(os.getenv("DATABASE_URL", "sqlite+pysqlite:///data/pass3-kpi-preview.db"))
