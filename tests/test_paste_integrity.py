"""Pass 3 positive controls, corruptions and integration tests. No paid API calls."""
from __future__ import annotations

import copy
import hashlib
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import ValidationError
from analyst.models import AnalystNote, QualityReport
from analyst.paste_evidence import EvidenceAnalystNote, EvidenceFact
from analyst.paste_integrity import assess_paste_integrity, locate_quote
from analyst.paste_quantities import (bound_preserved, calculate, scalar, supported_numbers, equal_at_display_precision)
from product.paste import PasteRequest, project_paste_result

ROOT = Path(__file__).resolve().parents[1]
from jobs.paste_test_cases import load_integrity_cases
CASES = load_integrity_cases()


def case(name='trt'):
    item = copy.deepcopy(next(c for c in CASES if c['id']==name))
    source = PasteRequest(text=item['source'])
    return source, EvidenceAnalystNote(source_id=source.source_id,**item['note'])


def codes(source,note):
    return {f.code for f in assess_paste_integrity(source.text,note).findings}


@pytest.mark.parametrize('name',['spr','trt'])
def test_supported_controls_preserve_display_and_have_real_spans(name):
    source,note=case(name)
    report=assess_paste_integrity(source.text,note)
    assert report.passed, report.feedback()
    assert report.checked_facts==len(note.key_facts)
    assert report.checked_claims==5+len(note.challenges_case)
    assert report.source_hash==source.source_hash
    for anchor in report.anchors:
        assert source.text[anchor['start']:anchor['end']]==anchor['quote']
    result=project_paste_result(source,note)
    assert result['headline']==note.headline
    assert result['source_verified'] is False
    assert result['facts'][0]['assertion']==note.key_facts[0].assertion
    assert note.materiality_evidence.scale_known is False
    assert note.impact_score==3  # unknown denominator does not automatically mean Minor


@pytest.mark.parametrize('quote,found',[
    ('Revenue £12.0m.',True),('Revenue  £12.0m.',True),
    ('Revenue £21.0m.',False),('revenue £12.0m.',False),('12.0',False)])
def test_quotes_match_words_numbers_and_whitespace_only(quote,found):
    assert (locate_quote('Header\nRevenue £12.0m.\nFooter',quote) is not None)==found


@pytest.mark.parametrize('mutation,expected',[
    ('unsupported-value','UNSUPPORTED_NUMBER'),
    ('fake-quote','QUOTE_NOT_FOUND'),
    ('missing-quote','MISSING_FACT_EVIDENCE'),
    ('expected-to-actual','EXPECTATION_AS_ACTUAL'),
    ('lost-expected','EXPECTED_QUALIFIER_LOST'),
    ('lost-bound','BOUND_CHANGED'),
    ('lost-condition','CONDITION_LOST'),
    ('unsupported-headline','UNSUPPORTED_CLAIM_NUMBER'),
    ('guaranteed-revenue','UNSUPPORTED_COMMITMENT'),
    ('missing-narrative','MISSING_CLAIM_EVIDENCE'),
    ('outside-source','OUTSIDE_SOURCE'),
    ('invented-high','HIGH_WITHOUT_BASIS'),
    ('invented-ratio','SCALE_DENOMINATOR_REQUIRED'),
    ('committed-materiality','MATERIALITY_CERTAINTY_CHANGED'),
    ('production-date','UNSUPPORTED_NUMBER'),
])
def test_corruptions_are_rejected(mutation,expected):
    source,note=case()
    f=note.key_facts[2]
    if mutation=='unsupported-value': f.value='>£7.0m'
    if mutation=='fake-quote': f.evidence_quotes=['The board expects annual revenues of more than £7.0m.']
    if mutation=='missing-quote': f.evidence_quotes=[]
    if mutation=='expected-to-actual': f.assertion='actual'
    if mutation=='lost-expected': f.label=f.metric='Annual revenue'
    if mutation=='lost-bound': f.value='£0.7m'
    if mutation=='lost-condition': f.note=''
    if mutation=='unsupported-headline': note.headline='Continental awards a £9m contract'
    if mutation=='guaranteed-revenue': note.headline='Continental guarantees £0.7m in contracted recurring revenue'
    if mutation=='missing-narrative': note.narrative_evidence=[]
    if mutation=='outside-source': note.source_references=['https://unprovided.invalid']
    if mutation=='invented-high':
        note.impact_score=4; note.materiality_evidence.basis='insufficient-context'
    if mutation=='invented-ratio': note.materiality_evidence.scale_known=True
    if mutation=='committed-materiality': note.materiality_evidence.certainty='committed'
    if mutation=='production-date': note.key_facts[1].value='From Q3 2027'
    assert expected in codes(source,note)


def test_no_evidence_subclass_cannot_pass_final_gate():
    source,note=case()
    old=AnalystNote.model_validate({k:v for k,v in note.model_dump().items()
        if k not in {'narrative_evidence','materiality_evidence'} and k!='key_facts'} | {'key_facts':[]})
    assert codes(source,old)=={'EVIDENCE_SCHEMA_REQUIRED'}


def test_springfield_year_end_cash_and_proposed_dividend_survive():
    source,note=case('spr')
    note.key_facts[2].as_of_date='15 September 2026'
    assert 'AS_OF_NOT_SUPPORTED' in codes(source,note)
    note.key_facts[2].as_of_date=''
    assert 'BALANCE_DATE_REQUIRED' in codes(source,note)
    note.key_facts[3].assertion='actual'
    assert 'PROPOSAL_AS_ACTUAL' in codes(source,note)


def test_post_period_payment_cannot_live_only_in_expanded_detail():
    source,note=case('spr')
    note.challenges_case=['Reported profit and EPS fell as land sales reduced.']
    # £20.7m is still an unselected fact. It must not vanish from the cash story.
    assert 'POST_PERIOD_CASH_OMITTED' in codes(source,note)


@pytest.mark.parametrize('shown,evidence,valid',[
    ('£1.2m','Group revenue £1,200k.',True),
    ('£1.2m','Group revenue £900k.',False),
    ('£1.2m','Group revenue $1.2m.',False),
    ('3.0p','The proposed dividend is 3.0p.',True),
    ('£243.7m','£000\nRevenue 243,699 280,557',True),
    ('50%','Dividend increase 50%.',True),
    ('6 months','This funded six-month programme.',True),
    ('£0','Cash was £0.',True),
    ('From Q3 2027','Production expected from Q2 2027.',False),
    ('-£1.2m','Net cash £1.2m.',False),
])
def test_quantity_scales_currency_dates_and_zero(shown,evidence,valid):
    assert supported_numbers(shown,evidence)==valid


@pytest.mark.parametrize('shown,evidence,valid',[
    ('>£0.7m','More than £0.7m annual revenue',True),
    ('£0.7m','More than £0.7m annual revenue',False),
    ('Up to £4m','Proposed funding of up to £4m',True),
    ('£4m','Proposed funding of up to £4m',False),
])
def test_bounds_are_not_converted_into_promises(shown,evidence,valid):
    assert bound_preserved(shown,evidence)==valid


@pytest.mark.parametrize('current,previous,result',[
    ('£1.2m','£900k','33.3%'),('£900k','£1.2m','-25%'),('3.0p','2.0p','50%')])
def test_arithmetic_normalises_units_before_comparison(current,previous,result):
    actual=calculate('percent-change',scalar(current),scalar(previous))
    assert equal_at_display_precision(scalar(result),actual)


@pytest.mark.parametrize('left,right',[
    ('£1.2m','$900k'),('£1.2m','£0'),('£1.2m','-£900k'),('Up to £4m','£1m')])
def test_ambiguous_or_invalid_arithmetic_is_rejected(left,right):
    with pytest.raises(ValueError): calculate('percent-change',scalar(left),scalar(right))


def calculated_dividend(source):
    quote='The board proposes a 3.0p dividend (2025: 2.0p), subject to shareholder approval.'
    return EvidenceFact(label='Proposed dividend increase',value='50%',basis='calculated',assertion='calculated',
        evidence_quotes=[quote],condition_quotes=['subject to shareholder approval.'],
        note='Calculated from 3.0p / 2.0p - 1. Subject to shareholder approval.',
        calculation={'operation':'percent-change','left':{'value':'3.0p','quote':quote},
                     'right':{'value':'2.0p','quote':quote},'comparable_basis':'Proposed total annual dividend per share versus prior year.'})


def test_calculated_dividend_requires_auditable_inputs():
    source,note=case('spr')
    note.key_facts.append(calculated_dividend(source))
    assert not codes(source,note),codes(source,note)
    note.key_facts[-1].value='60%'
    assert 'CALCULATION_MISMATCH' in codes(source,note)
    note.key_facts[-1].value='50%'
    note.key_facts[-1].calculation.left.value='4.0p'
    assert 'UNSUPPORTED_OPERAND' in codes(source,note)


def test_unsupported_guidance_upgrade_is_not_inferred_from_tone():
    source,note=case()
    from analyst.models import GuidanceEvent
    note.guidance_events=[GuidanceEvent(metric='profit',status='upgraded')]
    assert 'UNSUPPORTED_UPGRADE' in codes(source,note)


def _fake_sdk(monkeypatch,notes):
    calls=[]
    class Client:
        def __init__(self,**kwargs):
            self.responses=SimpleNamespace(parse=self.parse)
            self.options=[]; self.closed=False
        def with_options(self,**kwargs): self.options.append(kwargs); return self
        def close(self): self.closed=True
        def parse(self,**kwargs):
            calls.append(kwargs)
            return SimpleNamespace(output_parsed=notes[min(len(calls)-1,len(notes)-1)],
                                   usage=SimpleNamespace(input_tokens=100,output_tokens=200))
    monkeypatch.setitem(sys.modules,'openai',SimpleNamespace(OpenAI=Client))
    return calls


def test_bad_draft_uses_existing_review_and_the_same_evidence_schema(monkeypatch):
    from analyst.analyzer import OpenAIAnalystEngine
    from analyst.paste import build_pasted_announcement
    from analyst.paste_integrity import evidence_feedback
    from analyst.review_policy import ReviewDecision
    import analyst.analyzer as module
    source,good=case()
    bad=good.model_copy(deep=True); bad.key_facts[2].value='>£9m'
    calls=_fake_sdk(monkeypatch,[bad,good])
    monkeypatch.setattr(module,'decide_consistency_review',lambda *a,**kw: ReviewDecision(mode='single-pass',reasons=('test',)))
    engine=OpenAIAnalystEngine(api_key='test-only',model='test-only')
    engine.response_type=EvidenceAnalystNote; engine.draft_validator=evidence_feedback; engine.request_limit=2
    result=engine.analyse(build_pasted_announcement(source),prior_context=())
    assert len(calls)==2
    assert all(c['text_format'] is EvidenceAnalystNote and c['store'] is False for c in calls)
    assert 'UNSUPPORTED_NUMBER' in calls[1]['input']
    assert engine.last_review_decision.requires_review
    assert assess_paste_integrity(source.text,result).passed
    assert len(engine.usage_records)==2
    with pytest.raises(RuntimeError): engine._parse(model='test-only')
    assert len(calls)==2


@pytest.mark.parametrize('corrupt',[False,True])
def test_actual_adapter_final_gate_blocks_uncorrected_output(monkeypatch,corrupt):
    import analyst.paste as adapter
    source,note=case()
    if corrupt: note.key_facts[2].value='>£9m'
    calls=_fake_sdk(monkeypatch,[note])
    monkeypatch.setattr(adapter.Settings,'from_env',lambda: SimpleNamespace(
        openai_api_key='test-only',openai_model='test-only',openai_max_output_tokens=2000,prompt_version='test'))
    # Isolate the new final gate; the full engine's routed review still executes.
    monkeypatch.setattr(adapter,'assess_analysis_quality',lambda *a,**kw:QualityReport(status='publishable'))
    monkeypatch.setattr(adapter,'merge_monitoring_quality',lambda quality,note:quality)
    monkeypatch.setattr(adapter,'apply_analysis_guardrails',lambda announcement,note,**kw:note)
    if corrupt:
        with pytest.raises(adapter.PasteQualityError): adapter.analyse_paste(source)
    else:
        result=adapter.analyse_paste(source)
        assert result['integrity']['status']=='passed'
        assert result['versions']['evidence']=='paste-evidence-3'
        assert result['versions']['editorial']=='paste-editorial-2b'
        assert result['materiality_label']=='Material'
        assert result['telemetry']['requests']<=2
    assert len(calls)<=2


def test_evidence_schema_contains_no_arbitrary_calculation_code():
    schema=EvidenceAnalystNote.model_json_schema()
    assert schema['additionalProperties'] is False
    assert 'materiality_evidence' in schema['required']
    operations=schema['$defs']['EvidenceCalculation']['properties']['operation']['enum']
    assert operations==['percent-change','ratio','difference','sum']
    assert 'eval(' not in (ROOT/'analyst/paste_quantities.py').read_text()


def test_financial_year_cannot_be_advanced_for_display():
    source,note=case('spr')
    note.key_facts[0].period='FY27'
    assert 'PERIOD_NOT_SUPPORTED' in codes(source,note)


def test_customer_name_alone_does_not_justify_high_contract_rating():
    source,note=case()
    note.impact_score=4
    assert 'HIGH_OPERATIONAL_BASIS_UNCLEAR' in codes(source,note)


def test_critical_funding_is_not_downgraded_for_missing_denominator():
    source,note=case()
    source=PasteRequest(text=source.text+'\nThe company will enter administration unless further funding is secured.')
    note.source_id=source.source_id
    note.impact_score=5; note.materiality_evidence.basis='balance-sheet'
    note.materiality_evidence.evidence_quotes=['The company will enter administration unless further funding is secured.']
    assert 'SURVIVAL_RISK_UNDERRATED' not in codes(source,note)
    note.impact_score=1
    assert 'SURVIVAL_RISK_UNDERRATED' in codes(source,note)


def test_cash_from_gross_evidence_is_not_relabelled_net():
    source,note=case('spr')
    note.key_facts[2].evidence_quotes=['Revenue £243.7m (2025: £280.6m), adjusted PBT £12.9m (2025: £20.1m).']
    assert 'NET_BALANCE_BASIS_LOST' in codes(source,note)


def test_live_harness_requires_explicit_opt_in_and_credentials(monkeypatch,tmp_path):
    from jobs.check_paste_live import run
    monkeypatch.delenv('OPENAI_API_KEY',raising=False)
    output=tmp_path/'check.json'
    assert run(output=output)==0
    record=json.loads(output.read_text()); assert record['live_model'] is False
    assert record['status']=='preflight-only-no-model-request'
    assert run(output=output,live=True,model='test-only')==2
    assert json.loads(output.read_text())['status']=='blocked-missing-model-or-credential'
    with pytest.raises(ValueError):run(output=output,cases=('spr','trt','spr'))
    with pytest.raises(ValueError):run(output=output,max_output_tokens=999999)


def test_shortening_forecast_label_does_not_evade_assertion_check():
    source,note=case()
    fact=note.key_facts[2]; fact.assertion='actual'; fact.label='Revenue'
    assert 'EXPECTATION_AS_ACTUAL' in codes(source,note)


def test_quantified_headline_cannot_drop_more_than():
    source,note=case()
    note.headline='Transense expects £0.7m annual revenue from future deployments'
    assert 'CLAIM_BOUND_CHANGED' in codes(source,note)


def test_routine_non_numeric_holdout_does_not_require_invented_metrics():
    from analyst.models import WhatChanged
    source=PasteRequest(text='Example plc\n15 September 2026\nThe registered office address has changed. This administrative change does not affect trading, guidance or the company’s operations.')
    quote='The registered office address has changed. This administrative change does not affect trading, guidance or the company’s operations.'
    note=EvidenceAnalystNote(source_id=source.source_id,rns_type='Corporate',impact_colour='grey',
        impact_score=1,impact_level='low',impact_rationale='An administrative address change with no disclosed trading effect.',
        headline='Example changes its registered office address',takeaway='The registered office has changed. Trading and guidance are unaffected.',
        what_changed=WhatChanged(before='No independent history supplied.',today='The registered office address has changed.',read_through='Administrative change only.'),
        analyst_view='Administrative change only.',key_facts=[],
        narrative_evidence=[{'field':name,'index':0,'quotes':[quote]} for name in
            ['headline','takeaway','what_changed.today','analyst_view','impact_rationale']],
        materiality_evidence={'basis':'routine','certainty':'actual','horizon':'immediate','scale_known':False,'evidence_quotes':[quote]})
    assert assess_paste_integrity(source.text,note).passed


def test_ingestion_default_schema_and_review_policy_are_not_replaced(monkeypatch):
    from analyst.analyzer import OpenAIAnalystEngine
    _fake_sdk(monkeypatch,[])
    engine=OpenAIAnalystEngine(api_key='test-only',model='test-only')
    assert engine.response_type is AnalystNote
    assert engine.draft_validator is None
    assert engine.request_limit is None


def test_openai_sdk_can_build_strict_evidence_schema():
    pytest.importorskip('openai',reason='SDK verified in CI with pinned requirements')
    from openai.lib._pydantic import to_strict_json_schema
    schema=to_strict_json_schema(EvidenceAnalystNote)
    for definition in [schema,*schema.get('$defs',{}).values()]:
        if definition.get('type')=='object':
            assert definition['additionalProperties'] is False
            assert set(definition['required'])==set(definition['properties'])
