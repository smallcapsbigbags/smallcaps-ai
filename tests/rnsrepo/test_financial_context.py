"""Realistic copied-table regressions; live corpus tests are explicitly separate."""
from pathlib import Path
from types import SimpleNamespace
import json
import os
import pytest
from rnsrepo.financial_context import table_rows, table_metric_check, metric_reporting_quote, reporting_context
from rnsrepo.validation import check_card, forecast_applies
from rnsrepo.schema import CardDraft, CardError
from rnsrepo.sections import select_passages
from rnsrepo.extractor import request_kwargs, encoded_request_bytes
from rnsrepo.citations import citation_catalog, resolve_wire
from product.paste import PasteRequest
from test_card import statement

# Excerpts from the supplied Springfield release, not a pretend full annual report.
HEADER = 'Springfield Properties plc\nFinal Results\nThe results are for the year ended 31 May 2026.\n\n'
TABLE = ('Financial Highlights\n\n\t2026 £m\t2025 £m\tChange\n'
         'Revenue\t243.7\t280.6\t(13.2)%\n'
         'Profit before tax\t11.9\t19.0\t(37.4)%\n'
         'Adj. profit before tax*\t12.9\t20.1\t(35.8)%\n'
         'Net bank cash/(debt)\t1.2\t(20.9)\t-\n'
         'Total dividend per share (p)\t3.0p\t2.0p\t50.0%\n')
POST = 'The Group made the final deferred consideration payments of £20.7m post year end.'
PROPOSED = 'The proposed dividend of 3.0p is subject to shareholder approval.'
SOURCE = HEADER + TABLE + '\n' + POST + '\n\n' + PROPOSED


def metric(**kwargs):
    return SimpleNamespace(**{'label':'Adjusted PBT', 'value':'£12.9m', 'period':'Year ended 31 May 2026', **kwargs})

@pytest.mark.parametrize('layout', [lambda s:s, lambda s:s.replace('\t','\n\n'),lambda s:s.replace('\t','\n').replace('\n','\r\n')])
def test_table_columns_keep_label_units_year_and_original_spans(layout):
    source=layout(SOURCE);rows=table_rows(source)
    row=next(r for r in rows if r.label=='Adj. profit before tax*')
    assert row.years==('2026','2025') and row.values==('12.9','20.1')
    assert row.quantity(0).amount==12900000
    assert row.label in source[row.start:row.end]
    assert '2026' in source[row.header_start:row.header_end]
    assert not table_metric_check(metric(),source,rows)
    span=metric_reporting_quote(metric(),source,rows)
    assert source[span[0]:span[1]]=='year ended 31 May 2026'

@pytest.mark.parametrize('changes',[
    {'value':'£20.1m'}, {'value':'£11.9m'}, {'period':'2025'},
    {'label':'Revenue','value':'£280.6m','period':'2026'},
    {'label':'Net bank cash','value':'£20.9m','period':'2025'},
    {'label':'Proposed dividend','value':'£3m','period':'2026'},
])
def test_right_number_wrong_column_or_basis_is_not_accepted(changes):
    assert table_metric_check(metric(**changes),SOURCE,table_rows(SOURCE))==('TABLE_PERIOD_VALUE_MISMATCH',)


def test_date_context_does_not_accept_other_month_or_arbitrary_metric():
    rows=table_rows(SOURCE)
    assert metric_reporting_quote(metric(period='31 August 2026'),SOURCE,rows) is None
    assert metric_reporting_quote(metric(label='Order book'),SOURCE,rows) is None


def test_notes_column_is_not_a_year_value():
    source='2026 £000\n2025 £000\nRevenue\n3\n243699\n280557\nCost of sales\n203653\n228435'
    assert not table_rows(source)


def test_forecast_context_does_not_taint_actuals():
    evidence=('At 31 May 2026 the Group had net bank cash of £1.2m. '
              'This was ahead of external market forecasts of £10m of net bank debt.')
    assert not forecast_applies('Net bank cash £1.2m',evidence)
    assert not forecast_applies('Reduced profit for year ended 31 May 2026',evidence)
    assert not forecast_applies('Revenue £243.7m','Revenue was £243.7m, as expected.')
    assert forecast_applies('Revenue £10m','Revenue is expected to be £10m.')
    assert forecast_applies('Production Q2 2027','Production is expected from Q2 2027.')


def test_full_date_cannot_be_proved_by_three_unrelated_numbers():
    source='Example plc\nResults\nRevenue of £31m in May. The 2026 report discusses trading.'
    s=select_passages(source)
    c=CardDraft.model_validate({'announcement_type':'Results','headline':statement(s,'Results for 31 May 2026',source),
      'supporting_sentence':statement(s,'The company reports revenue.',source),'metrics':[], 'what_changed':None,'qualification':None})
    with pytest.raises(CardError) as e:check_card(source,s,c)
    assert 'UNSUPPORTED_DATE' in e.value.findings


def test_missing_date_on_row_gets_only_actual_report_header_and_anchors():
    s=select_passages(SOURCE); q=statement(s,'The company reports its annual results.',HEADER.strip())
    row_ref=statement(s,'dummy',TABLE.strip())['evidence']
    c=CardDraft.model_validate({'announcement_type':'Results','headline':q,'supporting_sentence':q,
      'metrics':[{'label':'Adjusted PBT','value':'£12.9m','period':'31 May 2026','note':'','evidence':row_ref}],
      'what_changed':None,'qualification':None})
    result=check_card(SOURCE,s,c)
    assert result['status']=='passed'
    assert any(a['field']=='metrics.0' and 'year ended 31 May 2026' in a['quote'] for a in result['anchors'])
    for a in result['anchors']:assert SOURCE[a['start']:a['end']]==a['quote']


def test_post_year_end_payment_before_timing_words_cannot_disappear():
    s=select_passages(SOURCE);q=statement(s,'The company reports results.',HEADER.strip())
    c=CardDraft.model_validate({'announcement_type':'Results','headline':q,'supporting_sentence':q,
      'metrics':[{'label':'Net bank cash','value':'£1.2m','period':'31 May 2026','note':'','evidence':statement(s,'dummy',TABLE.strip())['evidence']}],
      'what_changed':None,'qualification':None})
    with pytest.raises(CardError) as e:check_card(SOURCE,s,c)
    assert 'SUBSEQUENT_PAYMENT_OMITTED' in e.value.findings


def test_fixed_full_corpus_and_vertical_copy_preflight():
    directory=os.getenv('RNSREPO_CORPUS_DIR')
    if not directory:pytest.skip('Explicit full public source snapshots not supplied')
    from jobs.rnsrepo_corpus import load_corpus
    corpus=load_corpus(Path(directory))
    for name,text in corpus:
        for source in [text]+([text.replace('\t','\n\n')] if name=='spr-results' else []):
            kwargs,selection=request_kwargs(PasteRequest(text=source),'gpt-5-mini')
            assert encoded_request_bytes(kwargs)<=30000
            if name=='spr-results':
                assert len(source)>70000
                assert any('20.7' in p.text for p in selection.passages)
                rows=table_rows(source)
                assert any(r.label=='Adj. profit before tax*' for r in rows)
