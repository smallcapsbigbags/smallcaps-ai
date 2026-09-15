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


@pytest.mark.parametrize("change,expected", [
    ({"basis":"not-disclosed", "assertion":"not-disclosed", "value":"Not disclosed in this text"}, "DISCLOSURE_GAP_VALUE"),
    ({"basis":"calculated", "assertion":"calculated", "note":""}, "CALCULATION_NOTE_REQUIRED"),
    ({"value_low":7, "value_high":2}, "INVALID_FACT_RANGE"),
])
def test_cross_field_fact_errors_reach_review_but_never_pass_integrity(change,expected):
    from analyst.paste_integrity import assess_paste_integrity
    from analyst.models import KeyFact
    source,data=example()
    data["key_facts"][0].update(change)
    # Schema supports a repairable draft; no value is discarded or rewritten.
    note=EvidenceAnalystNote(**data)
    assert note.key_facts[0].value == data["key_facts"][0]["value"]
    report=assess_paste_integrity(source.text,note)
    assert not report.passed
    assert expected in {f.code for f in report.findings}
    assert any(expected in f for f in paste_review_feedback(build_pasted_announcement(source),note))
    legacy={k:v for k,v in note.key_facts[0].model_dump().items() if k in KeyFact.model_fields}
    with pytest.raises(ValidationError):
        KeyFact(**legacy)


def test_uncorrected_disclosure_gap_still_fails_final_gate(monkeypatch):
    from types import SimpleNamespace
    import analyst.paste as adapter
    source,data=example()
    data["key_facts"][-1].update(basis="not-disclosed",assertion="not-disclosed",value="Not specified")
    note=EvidenceAnalystNote(**data)
    class Engine:
        def __init__(self,**kwargs):
            self.model_name="test-only"
            self.client=SimpleNamespace(close=lambda:None)
            self.system_prompt=self.review_prompt=""
        def analyse(self,*args,**kwargs):
            return note
    monkeypatch.setattr(adapter,"OpenAIAnalystEngine",Engine)
    monkeypatch.setattr(adapter.Settings,"from_env",lambda:SimpleNamespace(
        openai_api_key="test-only",openai_model="test-only",openai_max_output_tokens=2000,prompt_version="test-only"))
    monkeypatch.setattr(adapter,"assess_analysis_quality",lambda *a,**kw:QualityReport(status="publishable"))
    monkeypatch.setattr(adapter,"merge_monitoring_quality",lambda q,*a,**kw:q)
    with pytest.raises(adapter.PasteQualityError):
        adapter.analyse_paste(source)



def test_live_funded_duration_is_not_misread_as_conditional_revenue():
    from analyst.paste_integrity import assess_paste_integrity
    source,data=example()
    fact=data["key_facts"][0]
    fact.update(label="Development phase",metric="Programme duration",value="Funded six month programme",
        basis="reported",assertion="actual",note="This is the funded initial phase before expected production.",
        evidence_quotes=["Following successful completion of this funded six month development programme,"],
        condition_quotes=["Following successful completion of this funded six month development programme,"])
    # A quantified revenue numerator can be known while its group denominator is not.
    data["materiality_evidence"].update(scale_known=False,amount_fact_index=2,denominator_fact_index=None)
    note=EvidenceAnalystNote(**data)
    checked=assess_paste_integrity(source.text,note)
    assert checked.passed,checked.feedback()
    assert note.key_facts[0].value==fact["value"]
    assert note.materiality_evidence.scale_known is False


@pytest.mark.parametrize("change",[
    {"assertion":"expected","label":"Expected production","metric":"Production start"},
    {"assertion":"actual","label":"Annual revenue","metric":"Annual revenue"},
    {"assertion":"proposed","label":"Proposed funding amount","metric":"Funding amount"},
    {"condition_quotes":["Subject to completion of development"]},
])
def test_duration_exception_never_hides_real_outcome_or_funding_conditions(change):
    from analyst.paste_integrity import _funded_duration_context
    from analyst.paste_evidence import EvidenceFact
    fact=dict(label="Development phase",metric="Programme duration",value="Funded six month programme",
        basis="reported",assertion="actual",note="Funded programme.",
        evidence_quotes=["Following successful completion of this funded six month development programme,"],
        condition_quotes=["Following successful completion of this funded six month development programme,"])
    fact.update(change)
    assert not _funded_duration_context(EvidenceFact(**fact))


@pytest.mark.parametrize("index",[-1,999])
def test_unknown_scale_does_not_allow_an_invalid_known_amount_reference(index):
    from analyst.paste_integrity import assess_paste_integrity
    source,data=example()
    data["materiality_evidence"].update(scale_known=False,amount_fact_index=index)
    report=assess_paste_integrity(source.text,EvidenceAnalystNote(**data))
    assert "SCALE_AMOUNT_INVALID" in {f.code for f in report.findings}


def test_unknown_scale_cannot_imply_a_known_denominator():
    from analyst.paste_integrity import assess_paste_integrity
    source,data=example()
    data["materiality_evidence"].update(scale_known=False,amount_fact_index=2,denominator_fact_index=0)
    report=assess_paste_integrity(source.text,EvidenceAnalystNote(**data))
    assert "SCALE_STATUS_CONFLICT" in {f.code for f in report.findings}
