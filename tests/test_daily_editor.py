from __future__ import annotations

from datetime import date, datetime, time

from product.daily_editor import DailyEditorCandidate, build_daily_editor


def candidate(
    source_id: str,
    *,
    ticker: str,
    title: str,
    rns_type: str,
    impact: int,
    signal: str = "AMBER",
    outlook: str = "N/A",
    verdict: str | None = None,
    analyst_view: str | None = None,
    minute: int = 0,
) -> DailyEditorCandidate:
    return DailyEditorCandidate(
        source_id=source_id,
        ticker=ticker,
        company=f"{ticker} plc",
        published_at=datetime.fromisoformat(f"2026-08-21T07:{minute:02d}:00+01:00"),
        rns_title=title,
        rns_type=rns_type,
        impact_score=impact,
        impact_level=("critical" if impact == 5 else "high" if impact >= 3 else "medium" if impact == 2 else "low"),
        signal=signal,
        outlook=outlook,
        verdict=verdict or f"{ticker} validated analyst verdict",
        what_changed=f"{ticker} changed today.",
        analyst_view=analyst_view or f"{ticker} validated analyst view.",
        source_url=f"https://example.invalid/{source_id}",
        analysis_version="aim-intelligence-analyst-3.3",
        prompt_version="analyst-engine-3.3-scbb-monitoring-sheet",
        model_version="recorded",
    )


def test_editor_allocates_attention_without_model_reasoning() -> None:
    page = build_daily_editor(
        day=date(2026, 8, 21),
        cutoff=time(12, 0),
        candidates=[
            candidate(
                "solvency",
                ticker="AAA",
                title="Notice of intention to appoint Administrators",
                rns_type="Funding & solvency",
                impact=5,
                signal="RED",
            ),
            candidate(
                "takeover",
                ticker="BBB",
                title="Possible Offer",
                rns_type="Takeover",
                impact=4,
            ),
            candidate(
                "contract",
                ticker="CCC",
                title="Contract Award",
                rns_type="Contracts",
                impact=2,
                signal="GREEN",
            ),
            candidate(
                "dealing",
                ticker="DDD",
                title="Director/PDMR Dealing",
                rns_type="Director dealing",
                impact=1,
                signal="NO COLOUR",
            ),
        ],
    )

    assert page.lead is not None
    assert page.lead.primary_source_id == "solvency"
    assert [item.primary_source_id for item in page.also_matters] == ["takeover"]
    assert [item.primary_source_id for item in page.quick_takes] == ["contract"]
    assert page.other_analysed_count == 1
    assert page.published_story_count == 3
    assert page.quiet_morning is False


def test_editor_allows_a_quiet_morning_instead_of_manufacturing_a_lead() -> None:
    page = build_daily_editor(
        day=date(2026, 8, 18),
        cutoff=time(12, 0),
        candidates=[
            candidate(
                "results",
                ticker="SNX",
                title="Interim Results",
                rns_type="Results & trading",
                impact=3,
                signal="GREEN",
                outlook="MAINTAINED",
            ),
            candidate(
                "board",
                ticker="QUBE",
                title="Board Change",
                rns_type="Board & advisers",
                impact=1,
                signal="NO COLOUR",
            ),
        ],
    )

    assert page.lead is None
    assert page.quiet_morning is True
    assert [item.primary_source_id for item in page.also_matters] == ["results"]
    assert page.quick_takes == []
    assert page.other_analysed_count == 1


def test_editor_consolidates_multiple_company_announcements_into_one_story() -> None:
    page = build_daily_editor(
        day=date(2026, 8, 21),
        cutoff=time(12, 0),
        candidates=[
            candidate(
                "gama-offer",
                ticker="GAMA",
                title="Response to press speculation",
                rns_type="Takeover",
                impact=4,
                minute=0,
            ),
            candidate(
                "gama-table",
                ticker="GAMA",
                title="Disclosure Table",
                rns_type="Takeover",
                impact=1,
                signal="NO COLOUR",
                minute=13,
            ),
        ],
    )

    assert page.lead is not None
    assert page.lead.primary_source_id == "gama-offer"
    assert set(page.lead.source_ids) == {"gama-offer", "gama-table"}
    assert page.candidate_count == 2
    assert page.published_story_count == 1
    assert page.other_analysed_count == 0
    assert any("consolidated" in reason for reason in page.lead.ranking_reasons)


def test_editor_does_not_invent_new_editorial_copy() -> None:
    verdict = "Balance sheet improves faster than earnings"
    view = "Good balance-sheet progress, but earnings guidance is unchanged."
    page = build_daily_editor(
        day=date(2026, 8, 21),
        cutoff=time(12, 0),
        candidates=[
            candidate(
                "balance-sheet",
                ticker="SPR",
                title="Trading Update",
                rns_type="Results & trading",
                impact=4,
                signal="GREEN",
                verdict=verdict,
                analyst_view=view,
            )
        ],
    )

    # This candidate scores 57, deliberately one point below the lead threshold.
    # The no-invention contract should not be weakened just to force a lead.
    assert page.lead is None
    assert len(page.also_matters) == 1
    story = page.also_matters[0]
    assert story.editorial_headline == verdict
    assert story.why_it_matters == view
