"""Regressions from bounded live deployment checks. No live API requests."""
import copy
import pytest
from pydantic import ValidationError
from analyst.models import AnalystNote, QualityReport, impact_level_from_score
from analyst.paste import build_pasted_announcement, paste_review_feedback
from analyst.paste_evidence import EvidenceAnalystNote
from jobs.paste_test_cases import load_integrity_cases
from product.paste import PasteRequest


def example():
    case = next(c for c in load_integrity_cases() if c["id"] == "trt")
    source = PasteRequest(text=case["source"])
    return source, {"source_id": source.source_id, **copy.deepcopy(case["note"])}


@pytest.mark.parametrize("score", range(1, 6))
@pytest.mark.parametrize("label", ["low", "medium", "high", "critical"])
def test_paste_derives_redundant_legacy_level_without_changing_judgement(score, label):
    source, data = example()
    data.update(impact_score=score, impact_level=label)
    note = EvidenceAnalystNote(**data)
    assert note.impact_score == score
    assert note.impact_level == impact_level_from_score(score)
    assert note.impact_colour == data["impact_colour"]
    assert note.headline == data["headline"]
    assert note.key_facts[0].value == data["key_facts"][0]["value"]


def test_invalid_score_still_fails_and_legacy_ingestion_stays_strict():
    source, data = example()
    with pytest.raises(ValidationError):
        EvidenceAnalystNote(**{**data, "impact_score": 6})
    note = EvidenceAnalystNote(**data)
    legacy = {k: v for k, v in note.model_dump().items() if k in AnalystNote.model_fields}
    legacy["key_facts"] = []
    legacy.update(impact_score=2, impact_level="low")
    with pytest.raises(ValidationError, match="impact_level must be 'medium'"):
        AnalystNote(**legacy)


def test_review_receives_existing_publication_gate_findings(monkeypatch):
    import analyst.paste as adapter
    source, data = example()
    note = EvidenceAnalystNote(**data)
    original = note.model_dump()
    monkeypatch.setattr(adapter, "assess_analysis_quality", lambda *a, **kw: QualityReport(
        status="review", flags=[{"code": "PUBLICATION_TEST", "severity": "review", "message": "Correct the disclosed comparison."}]))
    feedback = paste_review_feedback(build_pasted_announcement(source), note)
    assert any("PUBLICATION_TEST" in item for item in feedback)
    assert note.model_dump() == original


def test_review_receives_evidence_failures_too(monkeypatch):
    import analyst.paste as adapter
    source, data = example()
    data["key_facts"][0]["evidence_quotes"] = ["This passage was never in the source."]
    note = EvidenceAnalystNote(**data)
    monkeypatch.setattr(adapter, "assess_analysis_quality", lambda *a, **kw: QualityReport(status="publishable"))
    feedback = paste_review_feedback(build_pasted_announcement(source), note)
    assert any("QUOTE_NOT_FOUND" in item for item in feedback)
