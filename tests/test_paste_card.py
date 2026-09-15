"""Pass 2 display-policy tests; fixture notes are not live-model benchmarks."""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from analyst.models import AnalystNote
from product.paste import PasteRequest, project_paste_result
from product.paste_card import select_metric_indexes

ROOT = Path(__file__).resolve().parents[1]
CASES = json.loads((ROOT / "tests/fixtures/paste_card_cases.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["id"])
def test_card_projection_selects_highlights_without_rewriting_any_fact(case):
    source = PasteRequest(text=case["source"])
    note = AnalystNote(source_id=source.source_id, **case["note"])
    original = note.model_dump(mode="json")
    card = project_paste_result(source, note)
    assert card["metric_indexes"] == case["expected_metric_indexes"]
    assert card["facts"] == original["key_facts"]
    assert card["headline"] == note.headline
    assert card["summary"] == note.takeaway
    assert card["analyst_view"] == note.analyst_view
    assert card["what_changed"] == note.what_changed.today
    assert card["materiality"] == note.impact_score
    assert card["source_verified"] is False
    assert card["schema_version"] == "paste-mvp-2"
    assert card["card_layout_version"] == "paste-card-2"
    assert note.model_dump(mode="json") == original
    if case["id"] in {"trt", "sparse"}:
        assert card["identity"]["ticker"] is None
    if case["id"] == "sparse":
        assert card["identity"]["publication_date"] is None


def fact(label, value, **kwargs):
    return {"label": label, "metric": label.lower(), "value": value, "basis": "reported", **kwargs}


def test_sector_kpis_are_not_collapsed_into_one_other_bucket():
    facts = [fact("Recovery", "90%"), fact("Grade", "2.1 g/t"), fact("Utilisation", "80%"), fact("Throughput", "25 tonnes")]
    assert select_metric_indexes(facts, "Operations") == [0, 1, 2, 3]


def test_results_prefer_total_revenue_and_net_balance_without_calculation():
    facts = [fact("Private housing revenue", "£165m"), fact("Gross cash", "£24.2m"),
             fact("Adjusted PBT", "£12.9m"), fact("Group revenue", "£243.7m"),
             fact("Net bank cash", "£1.2m"), fact("Proposed dividend", "3.0p")]
    original = copy.deepcopy(facts)
    assert select_metric_indexes(facts, "Results & trading") == [3, 2, 4, 5]
    assert facts == original


def test_missing_figures_and_warnings_are_not_promoted_as_metric_tiles():
    facts = [fact("Margin", "Not disclosed", basis="not-disclosed"),
             fact("Source warning", "2026 source mismatch", basis="source-warning"),
             fact("Customer", "Continental"), fact("Revenue", "£0")]
    assert select_metric_indexes(facts, "Contracts") == [3]
    assert select_metric_indexes(facts[:-1], "Contracts") == []
    assert select_metric_indexes([], "Results & trading") == []
    assert select_metric_indexes(facts, "Contracts", limit=0) == []
    assert len(select_metric_indexes([fact(str(i), str(i)) for i in range(10)], "Other", limit=99)) == 4


def test_calculation_inputs_and_expected_proposed_periods_survive_projection():
    source = PasteRequest(text=CASES[0]["source"])
    payload = copy.deepcopy(CASES[0]["note"])
    payload["key_facts"] = [fact("Dividend increase", "50%", basis="calculated",
        note="Calculated from 3.0p / 2.0p - 1. Proposed and subject to approval.", period="FY26"),
        fact("Expected revenue", ">£0.7m", note="Conditional on development and deployment.", period="Future deployments")]
    note = AnalystNote(source_id=source.source_id, **payload)
    card = project_paste_result(source, note)
    for index in card["metric_indexes"]:
        assert card["facts"][index] == note.key_facts[index].model_dump(mode="json")
    assert card["facts"][0]["basis"] == "calculated"
    assert card["facts"][1]["value"] == ">£0.7m"


def test_card_assets_are_separate_and_loaded_before_the_controller():
    html = (ROOT / "frontend/analyse.html").read_text(encoding="utf-8")
    script = (ROOT / "frontend/assets/analysis-card.js").read_text(encoding="utf-8")
    controller = (ROOT / "frontend/assets/analyse.js").read_text(encoding="utf-8")
    css = (ROOT / "frontend/assets/analysis-card.css").read_text(encoding="utf-8")
    assert html.index('/assets/analysis-card.js?v={{ASSET_VERSION}}') < html.index('/assets/analyse.js?v={{ASSET_VERSION}}')
    assert '/assets/analysis-card.css?v={{ASSET_VERSION}}' in html
    assert "SmallcapsCard.render(result, card)" in controller
    for forbidden in ("innerHTML", "fetch(", "XMLHttpRequest", "localStorage", "eval("):
        assert forbidden not in script
    for forbidden in ("text-overflow: ellipsis", "line-clamp", "max-height:"):
        assert forbidden not in css
    assert 'section("What changed"' in script
    # Pass 2B presents qualifications without an editorial heading.
    assert 'section("What matters"' not in script
    assert "qualification-strip" in script
    assert "source-warning" in script
    assert "min-height: 44px" in css
