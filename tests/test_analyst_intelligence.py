from __future__ import annotations

from datetime import datetime, timezone

from analyst.intelligence import (
    detect_analytical_tensions,
    finding_is_resolved,
    unresolved_intelligence_findings,
)
from analyst.models import (
    AnalystNote,
    AnnouncementInput,
    DisclosureAssessment,
    KeyFact,
    WhatChanged,
)
from analyst.quality import assess_analysis_quality


def _announcement(
    *,
    source_id: str = "amco-1",
    ticker: str = "AMCO",
    company: str = "Amcomri Group plc",
    title: str = "Trading Update",
    text: str,
    rns_type: str = "Results & trading",
) -> AnnouncementInput:
    return AnnouncementInput(
        source_id=source_id,
        ticker=ticker,
        company=company,
        published_at=datetime(2026, 8, 22, 7, 0, tzinfo=timezone.utc),
        title=title,
        text=text,
        rns_type=rns_type,
        source_url=f"https://example.invalid/{source_id}",
        source_urls=[f"https://example.invalid/{source_id}"],
    )


def _amco_announcement() -> AnnouncementInput:
    return _announcement(
        text=(
            "Revenue increased to £42.4m from £31.8m. Adjusted EBITDA increased "
            "to £4.7m from £4.3m. Net debt increased to £2.5m from £2.0m. "
            "Growth included contributions from acquisitions and the group continues "
            "its buy-and-build strategy."
        )
    )


def _amco_note(*, resolved: bool) -> AnalystNote:
    analyst_view = (
        "Revenue grew, but adjusted EBITDA margin fell to 11.1% from 13.5% and "
        "net debt rose to £2.5m. Organic growth is not disclosed, so today's "
        "evidence weakens earnings quality despite the higher top line."
        if resolved
        else "Revenue growth strengthens the investment case."
    )
    disclosure = DisclosureAssessment(
        status="complete",
        missing_items=["Organic growth is not disclosed"] if resolved else [],
    )
    return AnalystNote(
        source_id="amco-1",
        rns_type="Results & trading",
        impact_colour="amber",
        impact_score=2,
        impact_level="medium",
        impact_rationale="Revenue rose, but the quality of growth needs testing.",
        headline="Revenue increases to £42.4m",
        takeaway="Revenue and adjusted EBITDA increased in the period.",
        key_facts=[
            KeyFact(
                label="Revenue",
                metric="revenue",
                period="FY26",
                value="£42.4m",
                value_numeric=42.4,
                previous_value="£31.8m",
                unit="million",
                currency="GBP",
                basis="reported",
            ),
            KeyFact(
                label="Adjusted EBITDA",
                metric="adjusted EBITDA",
                period="FY26",
                value="£4.7m",
                value_numeric=4.7,
                previous_value="£4.3m",
                unit="million",
                currency="GBP",
                basis="reported",
            ),
            KeyFact(
                label="Adjusted EBITDA margin",
                metric="adjusted EBITDA margin",
                period="FY26",
                value="11.1%",
                value_numeric=11.1,
                previous_value="13.5%",
                unit="%",
                basis="calculated",
                note=(
                    "Calculated from £4.7m / £42.4m = 11.1%; prior £4.3m / "
                    "£31.8m = 13.5%."
                ),
            ),
            KeyFact(
                label="Net debt",
                metric="net debt",
                period="Point in time",
                value="£2.5m",
                value_numeric=2.5,
                previous_value="£2.0m",
                unit="million",
                currency="GBP",
                basis="reported",
            ),
        ],
        what_changed=WhatChanged(
            before="Revenue was £31.8m and adjusted EBITDA was £4.3m.",
            today="Revenue is £42.4m and adjusted EBITDA is £4.7m.",
            read_through="The top line grew faster than profit.",
        ),
        analyst_view=analyst_view,
        disclosure_assessment=disclosure,
        source_references=["https://example.invalid/amco-1"],
        confidence=0.92,
    )


def test_growth_quality_cash_and_organic_tensions_are_detected() -> None:
    findings = detect_analytical_tensions(
        _amco_announcement(),
        _amco_note(resolved=False),
    )
    codes = {item.code for item in findings}

    assert "GROWTH_QUALITY_DIVERGENCE" in codes
    assert "EARNINGS_CASH_DIVERGENCE" in codes
    assert "ACQUISITION_ORGANIC_GAP" in codes


def test_resolved_note_clears_intelligence_review_flags() -> None:
    announcement = _amco_announcement()
    unresolved_note = _amco_note(resolved=False)
    resolved_note = _amco_note(resolved=True)

    _profile, unresolved = unresolved_intelligence_findings(
        announcement,
        unresolved_note,
    )
    assert {item.code for item in unresolved} >= {
        "GROWTH_QUALITY_DIVERGENCE",
        "EARNINGS_CASH_DIVERGENCE",
    }

    findings = detect_analytical_tensions(announcement, resolved_note)
    assert findings
    assert all(finding_is_resolved(item, resolved_note) for item in findings)

    bad_quality = assess_analysis_quality(announcement, unresolved_note)
    good_quality = assess_analysis_quality(announcement, resolved_note)
    assert bad_quality.status == "review"
    assert any(flag.code.startswith("INTELLIGENCE_") for flag in bad_quality.flags)
    assert good_quality.status == "publishable"
    assert not any(flag.code.startswith("INTELLIGENCE_") for flag in good_quality.flags)


def test_recruiter_nfi_disclosure_cannot_be_ignored() -> None:
    announcement = _announcement(
        source_id="rec-1",
        ticker="REC",
        company="Example Recruitment plc",
        text=(
            "The recruitment group reported contractor billings of £420m and net "
            "fee income of £43m. Sales headcount was 4% lower."
        ),
    )
    note = AnalystNote(
        source_id="rec-1",
        rns_type="Results & trading",
        impact_colour="green",
        impact_score=2,
        impact_level="medium",
        impact_rationale="Reported revenue increased.",
        headline="Revenue increases",
        takeaway="Gross contractor revenue increased in the period.",
        key_facts=[
            KeyFact(
                label="Gross contractor billings",
                metric="contractor billings",
                value="£420m",
                value_numeric=420,
                unit="million",
                currency="GBP",
                basis="reported",
            )
        ],
        what_changed=WhatChanged(
            before="Prior trading was weaker.",
            today="Billings increased.",
            read_through="The top line improved.",
        ),
        analyst_view="Higher billings strengthen the case.",
        source_references=["https://example.invalid/rec-1"],
        confidence=0.9,
    )

    findings = detect_analytical_tensions(announcement, note)

    assert any(item.code == "SECTOR_PRIMARY_KPI_OMITTED" for item in findings)


def test_life_sciences_funding_need_is_part_of_the_event() -> None:
    announcement = _announcement(
        source_id="bio-1",
        ticker="BIO",
        company="Example Therapeutics plc",
        title="Clinical and Funding Update",
        text=(
            "The Phase II clinical trial met its endpoint. The company requires "
            "further funding before the next milestone and no binding financing "
            "has been agreed. Cash runway extends to December."
        ),
        rns_type="Operations",
    )
    note = AnalystNote(
        source_id="bio-1",
        rns_type="Operations",
        impact_colour="green",
        impact_score=3,
        impact_level="high",
        impact_rationale="The trial met its endpoint.",
        headline="Phase II endpoint achieved",
        takeaway="The clinical study met its primary endpoint.",
        key_facts=[
            KeyFact(
                label="Trial result",
                metric="clinical endpoint",
                value="Met",
                basis="reported",
            )
        ],
        what_changed=WhatChanged(
            before="The trial was ongoing.",
            today="The endpoint was met.",
            read_through="Technical risk has reduced.",
        ),
        analyst_view="The result strengthens the investment case.",
        source_references=["https://example.invalid/bio-1"],
        confidence=0.9,
    )

    findings = detect_analytical_tensions(announcement, note)

    assert any(item.code == "LIFE_SCIENCE_FUNDING_GAP" for item in findings)


def test_memory_comparator_is_used_only_for_compatible_periods_and_basis() -> None:
    announcement = _announcement(
        source_id="mem-1",
        ticker="ABC",
        text="Revenue was £42.4m and adjusted EBITDA margin was 11.1%.",
    )
    note = AnalystNote(
        source_id="mem-1",
        rns_type="Results & trading",
        impact_colour="amber",
        impact_score=2,
        impact_level="medium",
        impact_rationale="Revenue improved but margin needs comparison.",
        headline="Revenue reaches £42.4m",
        takeaway="Revenue increased while margin was 11.1%.",
        key_facts=[
            KeyFact(
                label="Revenue",
                metric="revenue",
                period="FY26",
                value="£42.4m",
                value_numeric=42.4,
                unit="million",
                currency="GBP",
                basis="reported",
            ),
            KeyFact(
                label="Adjusted EBITDA margin",
                metric="adjusted EBITDA margin",
                period="FY26",
                value="11.1%",
                value_numeric=11.1,
                unit="%",
                basis="calculated",
                note="Calculated from £4.7m EBITDA / £42.4m revenue = 11.1%.",
            ),
        ],
        what_changed=WhatChanged(
            before="Earlier figures are in Company Memory.",
            today="Revenue is £42.4m and margin is 11.1%.",
            read_through="The relationship needs testing.",
        ),
        analyst_view="Revenue increased.",
        source_references=["https://example.invalid/mem-1"],
        confidence=0.9,
    )
    fy_memory = [
        {
            "context_type": "company_memory_snapshot",
            "metric_series": [
                {
                    "metric": "revenue",
                    "period_family": "FY",
                    "basis": "reported",
                    "unit": "million",
                    "currency": "GBP",
                    "points": [
                        {
                            "source_id": "old-revenue",
                            "value": "£31.8m",
                            "value_numeric": 31.8,
                        }
                    ],
                },
                {
                    "metric": "adjusted EBITDA margin",
                    "period_family": "FY",
                    "basis": "calculated",
                    "unit": "%",
                    "currency": "",
                    "points": [
                        {
                            "source_id": "old-margin",
                            "value": "13.5%",
                            "value_numeric": 13.5,
                        }
                    ],
                },
            ],
            "current_guidance": [],
            "open_management_claims": [],
            "resolved_management_claims": [],
        }
    ]
    h1_memory = [
        {
            **fy_memory[0],
            "metric_series": [
                {**item, "period_family": "H1"}
                for item in fy_memory[0]["metric_series"]
            ],
        }
    ]

    fy_codes = {
        item.code
        for item in detect_analytical_tensions(announcement, note, fy_memory)
    }
    h1_codes = {
        item.code
        for item in detect_analytical_tensions(announcement, note, h1_memory)
    }

    assert "GROWTH_QUALITY_DIVERGENCE" in fy_codes
    assert "GROWTH_QUALITY_DIVERGENCE" not in h1_codes
