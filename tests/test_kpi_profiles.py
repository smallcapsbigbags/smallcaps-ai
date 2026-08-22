from __future__ import annotations

from datetime import datetime, timezone

from analyst.kpi_profiles import infer_kpi_profile
from analyst.models import AnnouncementInput


def _announcement(
    *,
    ticker: str = "ABC",
    company: str = "Example plc",
    title: str = "Trading Update",
    text: str,
    rns_type: str = "Results & trading",
) -> AnnouncementInput:
    return AnnouncementInput(
        source_id=f"{ticker.lower()}-1",
        ticker=ticker,
        company=company,
        published_at=datetime(2026, 8, 22, 7, 0, tzinfo=timezone.utc),
        title=title,
        text=text,
        rns_type=rns_type,
        source_url=f"https://example.invalid/{ticker.lower()}-1",
    )


def test_housebuilder_profile_prioritises_volume_margin_and_debt() -> None:
    profile = infer_kpi_profile(
        _announcement(
            ticker="HOM",
            company="Example Homes plc",
            text=(
                "The housebuilder completed 1,240 homes. Private completions, "
                "average selling price, reservations, gross margin and the land bank "
                "were disclosed alongside net debt."
            ),
        )
    )

    assert profile.profile_id == "housebuilder"
    assert profile.confidence >= 0.7
    metrics = [item.metric for item in profile.priority_kpis]
    assert "Completions / reservations" in metrics
    assert "Gross / operating margin" in metrics
    assert "Net debt / net cash" in metrics


def test_recruiter_profile_uses_net_fee_income_not_pass_through_revenue() -> None:
    profile = infer_kpi_profile(
        _announcement(
            ticker="REC",
            company="Example Recruitment plc",
            text=(
                "Net fee income rose 8%. Contractor billings and permanent fees "
                "also changed, while sales headcount was reduced."
            ),
        )
    )

    assert profile.profile_id == "recruiter"
    assert profile.priority_kpis[0].metric == "Net fee income"
    assert "contractor payroll pass-through" in profile.priority_kpis[0].why


def test_structured_history_can_identify_software_profile_when_current_rns_is_generic() -> None:
    prior_context = [
        {
            "context_type": "company_memory_snapshot",
            "metric_series": [
                {"metric": "Annual recurring revenue", "label": "ARR"},
                {"metric": "Net revenue retention", "label": "NRR"},
                {"metric": "Cash burn", "label": "Cash burn"},
            ],
            "current_guidance": [],
            "open_management_claims": [],
            "resolved_management_claims": [],
        }
    ]
    profile = infer_kpi_profile(
        _announcement(
            ticker="SFT",
            company="Example Systems plc",
            text="The company provides an update on current trading.",
        ),
        prior_context,
    )

    assert profile.profile_id == "software"
    assert any(item.metric == "ARR / recurring revenue" for item in profile.priority_kpis)
    assert any("structured history" in item or "structured KPI" in item for item in profile.matched_signals)


def test_ambiguous_general_update_remains_generic() -> None:
    profile = infer_kpi_profile(
        _announcement(
            text="Revenue, profit and cash were disclosed for the period.",
        )
    )

    assert profile.profile_id == "generic"
    assert profile.confidence <= 0.5
    context = profile.to_context_record()
    assert context["context_type"] == "sector_kpi_profile"
    assert any("not a company-reported" in rule for rule in context["profile_rules"])
