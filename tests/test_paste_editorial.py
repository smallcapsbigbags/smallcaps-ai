"""Editorial contract tests. Manually authored fixtures are not a model-quality test."""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from analyst.models import AnalystNote, QualityReport
from analyst.paste_editorial import PASTE_CARD_EDITORIAL_INSTRUCTIONS, PASTE_EDITORIAL_VERSION
from product.paste import PasteRequest, project_paste_result

ROOT = Path(__file__).resolve().parents[1]
CASES = json.loads((ROOT / "tests/fixtures/paste_editorial_cases.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["id"])
def test_editorial_examples_keep_all_facts_and_qualifications(case):
    source = PasteRequest(text=case["source"])
    note = AnalystNote(source_id=source.source_id, **case["note"])
    original = note.model_dump(mode="json")
    card = project_paste_result(source, note)
    assert card["headline"] == note.headline
    assert card["summary"] == note.takeaway
    assert card["facts"] == original["key_facts"]
    assert card["metric_indexes"] == case["expected_metric_indexes"]
    assert card["what_matters"] == note.challenges_case
    assert note.model_dump(mode="json") == original
    if case["id"] == "spr":
        assert "£20.7m" in " ".join(card["what_matters"])
        assert card["facts"][2]["as_of_date"] == "31 May 2026"
        assert card["facts"][3]["label"] == "Proposed dividend"
    else:
        assert card["identity"]["ticker"] is None
        assert card["facts"][1]["value"] == "From Q2 2027"
        assert card["facts"][2]["label"] == "Expected annual revenue"
        assert "development and subsequent deployment" in " ".join(card["what_matters"])


def test_editorial_policy_is_applied_to_existing_generation_and_review(monkeypatch):
    import analyst.paste as adapter
    source = PasteRequest(text=CASES[1]["source"])
    captured = []
    class Engine:
        def __init__(self, **kwargs):
            self.model_name = kwargs["model"]
            self.system_prompt = "existing analyst rules"
            self.review_prompt = "existing review rules"
            self.client = SimpleNamespace(close=lambda: captured.append("closed"))
        def analyse(self, announcement, prior_context):
            captured.append((self.system_prompt, self.review_prompt, prior_context))
            return AnalystNote(source_id=source.source_id, **CASES[1]["note"])
    monkeypatch.setattr(adapter, "OpenAIAnalystEngine", Engine)
    monkeypatch.setattr(adapter.Settings, "from_env", lambda: SimpleNamespace(
        openai_api_key="test-only", openai_model="test-model", openai_max_output_tokens=2000, prompt_version="test-prompt"))
    monkeypatch.setattr(adapter, "apply_analysis_guardrails", lambda announcement, note, **kw: note)
    monkeypatch.setattr(adapter, "assess_analysis_quality", lambda *a, **kw: QualityReport(status="publishable"))
    monkeypatch.setattr(adapter, "merge_monitoring_quality", lambda report, note: report)
    result = adapter.analyse_paste(source)
    assert len(captured) == 2  # one engine entry, then closure; no new editorial model call
    for prompt in captured[0][:2]:
        assert "ON-DEMAND SOURCE BOUNDARY" in prompt
        assert PASTE_CARD_EDITORIAL_INSTRUCTIONS in prompt
    assert captured[0][2] == ()
    assert captured[-1] == "closed"
    assert result["versions"]["editorial"] == PASTE_EDITORIAL_VERSION


def test_editorial_renderer_does_not_clip_or_replace_financial_values():
    script = (ROOT / "frontend/assets/analysis-card.js").read_text(encoding="utf-8")
    css = (ROOT / "frontend/assets/analysis-card.css").read_text(encoding="utf-8")
    assert 'card.rns_type !== "Contracts"' in script
    assert 'section("What matters"' not in script
    assert "qualification-strip" in script
    assert "source-warning" in script
    assert 'card.versions?.editorial === "paste-editorial-2b"' in script
    for forbidden in ("innerHTML", "fetch(", "XMLHttpRequest", "localStorage", "eval("):
        assert forbidden not in script
    for forbidden in ("text-overflow: ellipsis", "line-clamp", "max-height:"):
        assert forbidden not in css
    assert "min-height: 44px" in css
    assert "width: 48px" in css
    assert "background: #fff8e9" in css
