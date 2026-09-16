"""Release regressions discovered in real calls, with adverse counterexamples.

Small sources below are explicit test excerpts, not claims of full-RNS live tests.
"""
import json
from pathlib import Path
import os
import pytest
from rnsrepo.schema import CardDraft, CardError
from rnsrepo.sections import select_passages
from rnsrepo.validation import check_card, is_balance, _numeric_text
from rnsrepo.financial_context import date_key, DATE
from rnsrepo.extractor import request_kwargs, encoded_request_bytes
from product.paste import PasteRequest
from test_card import statement, ref


def single(source, label, value, period='', note='', qualification=None):
    s=select_passages(source)
    headline=statement(s, 'The company announces an update.', source)
    c=CardDraft.model_validate({'announcement_type':'Other','headline':headline,
        'supporting_sentence':headline,
        'metrics':[{'label':label,'value':value,'period':period,'note':note,'evidence':[ref(s,source)]}],
        'what_changed':None,'qualification':statement(s,qualification,source) if qualification else None})
    return s,c


def fail(source, s, c, code):
    with pytest.raises(CardError) as err:check_card(source,s,c)
    assert code in err.value.findings
    return err.value


@pytest.mark.parametrize('rendered', ['2026-09-01','1 September 2026','01 Sep 2026'])
def test_director_date_equivalence_is_atomic(rendered):
    src='Example plc\nDirector dealing\nDate of the transaction: 2026.09.01. The director sold 66,930 shares at GBP 11.5554 per share.'
    s,c=single(src,'Shares sold','66,930 shares',rendered)
    assert check_card(src,s,c)['status']=='passed'
    c.metrics[0].period='2026-09-02'
    fail(src,s,c,'UNSUPPORTED_DATE')


@pytest.mark.parametrize('bad',['2026-99-01','2026.02.30','31 February 2026'])
def test_invalid_dates_never_self_validate(bad):
    assert date_key(bad) is None
    src=f'Example plc\nShares sold on {bad}: 120 shares.'
    s,c=single(src,'Shares sold','120 shares',bad)
    fail(src,s,c,'UNSUPPORTED_DATE')


@pytest.mark.parametrize('wording',['new Ordinary Shares','Vendor Shares','Placing Shares'])
def test_share_adjectives_do_not_destroy_count_units(wording):
    src=f'Example plc has issued 1,725,000,000 {wording} at an issue price of 0.06 pence per share.'
    s,c=single(src,'Shares issued','1,725,000,000 shares')
    assert check_card(src,s,c)['status']=='passed'
    c.metrics[0].value='1,725,000 shares'
    fail(src,s,c,'UNSUPPORTED_NUMBER')
    c.metrics[0].value='£1,725,000,000'
    fail(src,s,c,'UNSUPPORTED_NUMBER')


def test_loss_magnitude_does_not_turn_loss_into_profit():
    src='Example plc reported an operating loss of £(772,958) for the six months ended 30 June 2026.'
    s,c=single(src,'Operating loss','£772,958','Six months ended 30 June 2026')
    assert check_card(src,s,c)['status']=='passed'
    c.metrics[0].label='Operating profit'
    fail(src,s,c,'UNSUPPORTED_NUMBER')
    c.metrics[0].label='Operating loss';c.metrics[0].value='£876,634'
    fail(src,s,c,'UNSUPPORTED_NUMBER')


@pytest.mark.parametrize('label',['Cash element','Cash receipts','Disposal cash proceeds'])
def test_transaction_cash_is_not_a_balance(label):
    src='Example plc reports a cash element of €90m for the transaction. Disposal cash receipts were €90m.'
    s,c=single(src,label,'€90m')
    assert not is_balance(label)
    assert check_card(src,s,c)['status']=='passed'
    c.metrics[0].label='Cash balance'
    fail(src,s,c,'BALANCE_DATE_REQUIRED')


def test_disclosed_reduction_is_equivalent_not_a_new_percentage():
    src='Group revenue was £188.8m, a reduction of 22.8% compared with the prior period.'
    s,c=single(src,'Revenue change','down 22.8%')
    assert check_card(src,s,c)['status']=='passed'
    c.metrics[0].value='22.8%'
    fail(src,s,c,'UNSUPPORTED_NUMBER')


def test_future_acquisition_condition_does_not_taint_past_target_revenue():
    src=('Dolomitas reported revenue of €70m for the year ended 31 December 2025. '
         'The acquisition is expected to complete in Q4 2026 subject to regulatory consents.')
    s,c=single(src,'Reported revenue','€70m','Year ended 31 December 2025')
    assert check_card(src,s,c)['status']=='passed'


def test_condition_on_actual_price_cannot_be_discarded():
    src='The acquisition consideration is €110m subject to regulatory consents.'
    s,c=single(src,'Acquisition consideration','€110m')
    fail(src,s,c,'CONDITION_LOST')


def test_do_not_approve_a_computed_acquisition_total():
    src='The acquisition consideration is €110m with a further €8m for non-core assets.'
    s,c=single(src,'Consideration','€118m')
    fail(src,s,c,'UNSUPPORTED_NUMBER')


def test_unsupported_numbers_have_safe_field_diagnostics():
    src='The acquisition consideration is €110m with a further €8m for non-core assets.'
    s,c=single(src,'Consideration','€118m')
    err=fail(src,s,c,'UNSUPPORTED_NUMBER')
    assert {'field':'metrics.0','code':'UNSUPPORTED_NUMBER'} in err.details
    assert all(set(d)=={'field','code'} for d in err.details)
    assert '110m' not in json.dumps(err.details)


def test_correction_cannot_disappear():
    src=('Example plc\nThe following amendment has been made to the results announcement. '
         'The gross margin figure should be 58.3% rather than 53%.')
    s,c=single(src,'Gross margin','58.3%')
    fail(src,s,c,'CORRECTION_OMITTED')
    c.headline.text='The company corrects its gross margin figure.'
    assert check_card(src,s,c)['status']=='passed'


def test_full_springfield_obligations_and_table_context_are_in_small_packet():
    directory=os.getenv('RNSREPO_CORPUS_DIR')
    if not directory:pytest.skip('Full public source snapshots not available')
    from jobs.rnsrepo_corpus import load_corpus
    full=dict(load_corpus(Path(directory)))['spr-results']
    for src in (full,full.replace('\t','\n\n')):
        kwargs,selection=request_kwargs(PasteRequest(text=src),'gpt-5-mini')
        payload=json.loads(kwargs['input'])
        assert encoded_request_bytes(kwargs)<=30000
        assert selection.reduced and len(src)>70000
        assert any('20.7' in json.dumps(item) for item in payload['required_context'])
        assert any('dividend' in item['label'].lower() for item in payload['financial_rows'])
        assert '31 May 2026' in payload['reporting_period']['text']
        assert all(selection.source_characters==len(src) for _ in [0])
