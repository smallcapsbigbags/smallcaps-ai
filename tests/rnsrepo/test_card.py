from __future__ import annotations
import copy
import json
from types import SimpleNamespace
import pytest
from pydantic import ValidationError
from product.paste import PasteRequest
from rnsrepo.schema import CardDraft, CardError
from rnsrepo.sections import select_passages, MAX_EXCERPT_BYTES
from rnsrepo.validation import check_card
from rnsrepo.extractor import CardExtractor, request_kwargs, MAX_REQUEST_BYTES, MAX_OUTPUT_TOKENS

TRT = '''RNS Number : 7173U
Transense Technologies PLC
15 September 2026

Contract award with Continental to develop next-generation tyre management tool

Transense has secured a development and supply contract with Continental.
Translogik will develop a bespoke version of its handheld TLGX device.
The funded development programme lasts six months.
Production is expected from Q2 2027 following successful development.
The board expects annual revenues of more than £0.7m from future deployments,
subject to successful completion of the development project.
'''

SPR = '''RNS Number : 1234U
Springfield Properties plc
15 September 2026

Final Results
Financial Highlights
Revenue for 2026 was £243.7m versus £280.6m in 2025.
Adjusted profit before tax was £12.9m for 2026 versus £20.1m for 2025.
Net bank cash at 31 May 2026 was £1.2m, versus £20.9m net bank debt at 31 May 2025.
The board proposes a 3.0p dividend, subject to shareholder approval.
Private and affordable housing revenue increased while land sales fell.

Outlook
Private housing reservations remain steady.

Subsequent events
After year-end the group paid £20.7m of deferred acquisition consideration.
'''

def ref(selection, quote):
    p = next(p for p in selection.passages if quote in p.text)
    return {"passage_id": p.id, "quote": quote}

def statement(selection, text, *quotes):
    return {"text": text, "evidence": [ref(selection, q) for q in quotes]}

def draft(text=TRT):
    s = select_passages(text)
    award = 'Transense has secured a development and supply contract with Continental.'
    conditions = 'The board expects annual revenues of more than £0.7m from future deployments,\nsubject to successful completion of the development project.'
    data = {"announcement_type": "Contract",
        "headline": statement(s, "Continental awards development and supply contract", award),
        "supporting_sentence": statement(s, "Translogik will develop a bespoke version of its TLGX handheld device.",
            'Translogik will develop a bespoke version of its handheld TLGX device.'),
        "metrics": [
            {"label": "Development programme", "value": "6 months", "period": "", "note": "Funded programme.",
             "evidence": [ref(s, 'The funded development programme lasts six months.')]},
            {"label": "Expected production", "value": "Q2 2027", "period": "", "note": "Following successful development.",
             "evidence": [ref(s, 'Production is expected from Q2 2027 following successful development.')]},
            {"label": "Expected annual revenue", "value": ">£0.7m", "period": "Future deployments",
             "note": "Subject to successful completion of development.", "evidence": [ref(s, conditions)]}],
        "what_changed": None,
        "qualification": statement(s, "Future revenues are expected from deployments, subject to successful development.", conditions)}
    return s, CardDraft.model_validate(data)


def response(card, **override):
    value = {"status": "completed", "output": [{"type": "message", "content": [
        {"type": "output_text", "text": card.model_dump_json()}]}],
        "usage": {"input_tokens": 1200, "output_tokens": 700,
                  "output_tokens_details": {"reasoning_tokens": 100},
                  "input_tokens_details": {"cached_tokens": 0}}}
    value.update(override); return value

class Client:
    def __init__(self, output=None, error=None):
        self.output, self.error = output, error
        self.calls = []; self.options = None; self.closed = False
        self.responses = self
    def factory(self, **options): self.options = options; return self
    def __enter__(self): return self
    def __exit__(self, *args): self.closed = True
    def create(self, **kwargs):
        self.calls.append(kwargs)
        if self.error: raise self.error
        return self.output


def test_card_is_six_fields_without_analyst_scoring():
    assert set(CardDraft.model_fields) == {"announcement_type", "headline", "supporting_sentence", "metrics", "what_changed", "qualification"}
    schema = CardDraft.model_json_schema()
    assert schema['additionalProperties'] is False
    assert 'materiality' not in json.dumps(schema)
    _, c = draft()
    with pytest.raises(ValidationError): CardDraft.model_validate({**c.model_dump(), "impact_score": 3})


def test_short_complete_source_and_missing_ticker():
    selection, card = draft()
    assert not selection.reduced
    checked = check_card(TRT, selection, card)
    assert checked['status'] == 'passed'
    for a in checked['anchors']: assert TRT[a['start']:a['end']] == a['quote']
    client = Client(response(card))
    result = CardExtractor('test-not-secret', client_factory=client.factory).extract(PasteRequest(text=TRT))
    assert len(client.calls) == 1 and client.closed
    assert client.options['max_retries'] == 0
    assert client.calls[0]['reasoning'] == {'effort':'minimal'}
    assert client.calls[0]['store'] is False
    assert result['identity']['ticker'] is None
    assert result['headline'] == card.headline.text
    assert result['facts'][2]['value'] == '>£0.7m'
    assert 'materiality' not in result and 'direction' not in result
    assert result['capabilities']['questions'] is False
    assert result['telemetry']['input_tokens'] == 1200


def test_long_document_scans_tail_without_sending_all_text():
    filler = ('Accounting policies\nThe group applies consistent accounting policies to these items.\n\n' * 900)
    text = SPR.split('Subsequent events')[0] + filler + '\nSubsequent events\nAfter year-end the group paid £20.7m of deferred acquisition consideration.'
    assert 70000 < len(text) < 120000
    packet, selected = request_kwargs(PasteRequest(text=text), 'gpt-5-mini')
    assert selected.reduced
    assert selected.selected_bytes <= MAX_EXCERPT_BYTES
    assert selected.selected_characters < len(text) / 3
    assert '£20.7m' in packet['input'] and '£243.7m' in packet['input']
    assert packet['model'] == 'gpt-5-mini'
    assert len(json.dumps(packet, ensure_ascii=False,separators=(',',':')).encode()) <= MAX_REQUEST_BYTES
    assert packet['max_output_tokens'] == MAX_OUTPUT_TOKENS
    for p in selected.passages: assert text[p.start:p.end] == p.text

@pytest.mark.parametrize('chars', [120, 1200, 5000, 19000, 77609, 119999])
def test_selection_offsets_and_budget(chars):
    text = ('Ordinary report. No financial claim here.\n\n' * (chars//30 + 2))[:chars]
    selection = select_passages(text)
    assert selection.selected_bytes <= MAX_EXCERPT_BYTES
    for p in selection.passages: assert text[p.start:p.end] == p.text


def test_many_material_passages_fail_locally_not_silently_drop():
    text = '\n\n'.join(f'Material uncertainty about item {i}. ' + 'Other information. '*70 for i in range(60))
    with pytest.raises(CardError, match='CARD_SELECTION'): select_passages(text)

@pytest.mark.parametrize('edit,code', [
    (lambda c: setattr(c.metrics[2], 'value', '£0.7m'), 'BOUND_CHANGED'),
    (lambda c: setattr(c.metrics[2], 'value', '>£7m'), 'UNSUPPORTED_NUMBER'),
    (lambda c: setattr(c.metrics[1], 'value', 'Q3 2027'), 'UNSUPPORTED_NUMBER'),
    (lambda c: setattr(c.metrics[2], 'label', 'Guaranteed annual revenue'), 'UNSUPPORTED_COMMITMENT'),
    (lambda c: setattr(c.metrics[0].evidence[0], 'quote', 'The funded development programme lasts twelve months.'), 'QUOTE_NOT_FOUND'),
    (lambda c: setattr(c.metrics[0].evidence[0], 'passage_id', 'p99999'), 'UNKNOWN_PASSAGE'),
    (lambda c: setattr(c.headline, 'text', 'Continental pays £50m'), 'UNSUPPORTED_NUMBER'),
])
def test_corruptions_rejected_without_repair_request(edit, code):
    s, c = draft(); edit(c)
    with pytest.raises(CardError) as err: check_card(TRT, s, c)
    assert code in err.value.findings


def test_qualification_in_another_tile_does_not_repair_metric():
    s,c=draft(); c.metrics[2].label='Annual revenue'; c.metrics[2].note=''
    with pytest.raises(CardError) as err: check_card(TRT,s,c)
    assert 'EXPECTED_QUALIFIER_LOST' in err.value.findings
    assert 'CONDITION_LOST' in err.value.findings


def test_balance_dates_and_post_period_payment():
    s=select_passages(SPR)
    revenue='Revenue for 2026 was £243.7m versus £280.6m in 2025.'
    cash='Net bank cash at 31 May 2026 was £1.2m, versus £20.9m net bank debt at 31 May 2025.'
    later='After year-end the group paid £20.7m of deferred acquisition consideration.'
    c=CardDraft.model_validate({"announcement_type":"Results",'headline':statement(s,'Springfield reports annual revenue',revenue),
        'supporting_sentence':statement(s,'Revenue for 2026 was £243.7m.',revenue),
        'metrics':[{'label':'Net bank cash','value':'£1.2m','period':'31 May 2026','note':'','evidence':[ref(s,cash)]}],
        'what_changed':None,'qualification':statement(s,later,later)})
    assert check_card(SPR,s,c)['status']=='passed'
    c.qualification=None
    with pytest.raises(CardError) as err:check_card(SPR,s,c)
    assert 'SUBSEQUENT_PAYMENT_OMITTED' in err.value.findings
    c.metrics[0].period=''
    with pytest.raises(CardError) as err:check_card(SPR,s,c)
    assert 'BALANCE_DATE_REQUIRED' in err.value.findings

@pytest.mark.parametrize('status,parts,expected', [
    ('incomplete',[], 'CARD_INCOMPLETE'),
    ('failed',[], 'CARD_PROVIDER'),
    ('completed',[{'type':'message','content':[{'type':'refusal','refusal':'no'}]}],'CARD_REFUSED'),
    ('completed',[{'type':'message','content':[{'type':'output_text','text':'{'}]}],'CARD_FORMAT'),
    ('completed',[], 'CARD_FORMAT'),
])
def test_structured_response_failure_is_bounded(status,parts,expected):
    client=Client({'status':status,'output':parts})
    with pytest.raises(CardError,match=expected):
        CardExtractor('test',client_factory=client.factory).extract(PasteRequest(text=TRT))
    assert len(client.calls)==1 and client.closed

@pytest.mark.parametrize('status,code,name,expected', [
    (429,'insufficient_quota','RateLimitError','CARD_QUOTA'),
    (429,'rate_limit_exceeded','RateLimitError','CARD_RATE_LIMIT'),
    (None,None,'APITimeoutError','CARD_TIMEOUT'),
    (401,None,'AuthenticationError','CARD_CONFIGURATION'),
    (500,None,'InternalServerError','CARD_PROVIDER'),
])
def test_provider_failures_never_escalate_or_leak(caplog,status,code,name,expected):
    exc=type(name,(Exception,),{'status_code':status,'code':code})('PRIVATE KEY SECRET SOURCE')
    client=Client(error=exc)
    with pytest.raises(CardError,match=expected):
        CardExtractor('API-SECRET',client_factory=client.factory).extract(PasteRequest(text=TRT))
    assert len(client.calls)==1
    assert 'PRIVATE KEY' not in caplog.text and 'API-SECRET' not in caplog.text and '£0.7m' not in caplog.text


def test_no_automatic_flagship_even_for_long_source():
    with pytest.raises(CardError,match='CARD_CONFIGURATION'):
        request_kwargs(PasteRequest(text=TRT), 'gpt-5.4')


def test_no_arithmetic_or_invented_metrics_required():
    s,c=draft();c.metrics=[]
    assert check_card(TRT,s,c)['status']=='passed'


def test_repeated_later_payment_is_not_repeated_citation_requirement():
    s=select_passages(SPR + '\nSubsequent events\nAfter year-end the group paid £20.7m of deferred acquisition consideration.')
    source=SPR + '\nSubsequent events\nAfter year-end the group paid £20.7m of deferred acquisition consideration.'
    cash='Net bank cash at 31 May 2026 was £1.2m, versus £20.9m net bank debt at 31 May 2025.'
    later='After year-end the group paid £20.7m of deferred acquisition consideration.'
    c=CardDraft.model_validate({'announcement_type':'Results','headline':statement(s,'Springfield reports net bank cash',cash),
        'supporting_sentence':statement(s,cash,cash),'metrics':[{'label':'Net bank cash','value':'£1.2m','period':'31 May 2026','note':'','evidence':[ref(s,cash)]}],
        'what_changed':None,'qualification':statement(s,later,later)})
    assert check_card(source,s,c)['status']=='passed'


def test_api_default_runner_is_compact_and_not_analyst():
    from api.paste import default_jobs
    default_jobs.cache_clear()
    jobs=default_jobs()
    try: assert jobs.runner.__module__=='rnsrepo.extractor'
    finally: jobs.close();default_jobs.cache_clear()


def test_failed_job_retains_specific_safe_code():
    from api.paste_jobs import PasteJobs
    import time
    def fail(source): raise CardError('CARD_QUOTA')
    jobs=PasteJobs(fail)
    try:
        job=jobs.submit('one',PasteRequest(text=TRT))
        for _ in range(100):
            got=jobs.get('one',job['analysis_id'])
            if got['status']!='processing':break
            time.sleep(.01)
        assert got['status']=='failed' and got['error_code']=='CARD_QUOTA'
        assert jobs.get('someone-else',job['analysis_id']) is None
    finally:jobs.close()


def test_compact_card_cannot_start_legacy_question_calls():
    from api.paste_jobs import PasteJobs
    from api.paste_conversations import FollowupJobs, ConversationMissing
    import time
    _,c=draft();client=Client(response(c))
    jobs=PasteJobs(CardExtractor('test',client_factory=client.factory).extract)
    chat_calls=[]
    followups=FollowupJobs(jobs,lambda *a:chat_calls.append(a))
    try:
        job=jobs.submit('one',PasteRequest(text=TRT))
        for _ in range(100):
            got=jobs.get('one',job['analysis_id'])
            if got['status']!='processing':break
            time.sleep(.01)
        assert got['status']=='complete'
        with pytest.raises(ConversationMissing):followups.history('one',job['analysis_id'])
        assert not chat_calls
    finally:followups.close();jobs.close()


def test_unrelated_openai_fallback_settings_do_not_change_card_model(monkeypatch):
    import rnsrepo.extractor as mod
    seen=[]
    class Extractor:
        def __init__(self,key,model):seen.append(model)
        def extract(self,source):return {}
    monkeypatch.setenv('OPENAI_MODEL','gpt-5.4')
    monkeypatch.setenv('OPENAI_PASTE_FALLBACK_MODEL','gpt-5.4')
    monkeypatch.delenv('RNSREPO_CARD_MODEL',raising=False)
    monkeypatch.setattr(mod,'CardExtractor',Extractor)
    mod.extract_card(PasteRequest(text=TRT))
    assert seen==['gpt-5-mini']


def test_request_has_no_tools_and_no_full_source_for_long_input():
    source=PasteRequest(text=TRT + '\n\n' + ('Ordinary accounting-policy text without new figures. '*1600))
    kwargs, selection=request_kwargs(source,'gpt-5-nano')
    assert 'tools' not in kwargs
    assert 'original_source' not in kwargs['input']
    assert source.text not in kwargs['input']
    assert kwargs['model']=='gpt-5-nano'
    assert kwargs['max_output_tokens']==3000


def test_diagnostic_preflight_cannot_spend(monkeypatch,capsys):
    from jobs.check_rnsrepo_card import run
    def no_call(*a,**kw):raise AssertionError('Paid request during preflight')
    monkeypatch.setattr(CardExtractor,'extract',no_call)
    assert run()==0
    record=json.loads(capsys.readouterr().out)
    assert record['live'] is False and record['status']=='preflight-only'


def test_development_revenue_is_not_exempt_from_condition_checks():
    s,c=draft();c.metrics[2].label='Expected development revenue';c.metrics[2].note=''
    with pytest.raises(CardError) as err:check_card(TRT,s,c)
    assert 'CONDITION_LOST' in err.value.findings


def test_critical_condition_remains_on_primary_qualification_strip():
    s,c=draft();c.qualification=None
    with pytest.raises(CardError) as err:check_card(TRT,s,c)
    assert 'QUALIFICATION_MISSING' in err.value.findings


def test_gross_cash_cannot_become_net_cash():
    source=SPR.replace('Net bank cash at 31 May 2026 was £1.2m, versus £20.9m net bank debt at 31 May 2025.',
        'Cash at 31 May 2026 was £24.1m.').split('Subsequent events')[0]
    s=select_passages(source);cash='Cash at 31 May 2026 was £24.1m.'
    c=CardDraft.model_validate({'announcement_type':'Results','headline':statement(s,'Cash balance reported',cash),
        'supporting_sentence':statement(s,cash,cash),'metrics':[{'label':'Net cash','value':'£24.1m','period':'31 May 2026','note':'','evidence':[ref(s,cash)]}],
        'what_changed':None,'qualification':None})
    with pytest.raises(CardError) as err:check_card(source,s,c)
    assert 'NET_BASIS_MISSING' in err.value.findings


def test_real_sdk_response_round_trip_without_network():
    openai = pytest.importorskip('openai')
    if not hasattr(openai, 'OpenAI'):
        pytest.skip('Real OpenAI SDK installed in CI, unavailable in this local runtime')
    import httpx
    _, c = draft()
    body = response(c)
    body.update(id='resp_mock', object='response', created_at=1, model='gpt-5-mini')
    seen = []
    def handle(request):
        seen.append(json.loads(request.content))
        return httpx.Response(200, json=body)
    def factory(**kwargs):
        return openai.OpenAI(**kwargs, http_client=httpx.Client(transport=httpx.MockTransport(handle)))
    result = CardExtractor('test-only', client_factory=factory).extract(PasteRequest(text=TRT))
    assert result['headline'] == c.headline.text
    assert len(seen) == 1
    assert seen[0]['text']['format']['strict'] is True
    assert 'tools' not in seen[0]
