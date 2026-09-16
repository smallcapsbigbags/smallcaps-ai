"""Contraction regression controls. Local code tests are not live-model evidence."""
import json
from pathlib import Path
import pytest
from product.paste import PasteRequest, extract_identity
from rnsrepo.extractor import request_kwargs, encoded_request_bytes, MAX_REQUEST_BYTES
from rnsrepo.sections import select_passages
from rnsrepo.validation import check_card, _numeric_text
from rnsrepo.schema import CardDraft, CardError, Statement
from analyst.paste_quantities import supported_numbers, bound_preserved
from jobs.rnsrepo_corpus import issuer_text
from test_card import statement, ref


def test_complete_request_budget_includes_reference_schema_and_escaping():
    # Many short financial rows previously inflated reference metadata. Keep a
    # real late risk inside a synthetic long fixture and never discard that risk.
    text = ('Example plc\n16 September 2026\nFinal results\n\nFinancial Highlights\n\n'
            + '\n\n'.join('Revenue row %s 2026 £%sm' % (i,i) for i in range(900))
            + '\n\nGoing concern\nA material uncertainty exists which may cast significant doubt on going concern. Additional funding is needed.')
    kwargs, selection = request_kwargs(PasteRequest(text=text), 'gpt-5-mini')
    assert encoded_request_bytes(kwargs) <= MAX_REQUEST_BYTES
    assert any('material uncertainty exists' in p.text for p in selection.passages)
    assert selection.reduced


def test_cannot_shrink_away_mandatory_risk_to_fit_budget():
    text = '\n\n'.join('Material uncertainty exists. '+('Funding context. '*65)+str(i) for i in range(60))
    with pytest.raises(CardError, match='CARD_SELECTION'):
        request_kwargs(PasteRequest(text=text), 'gpt-5-mini')


@pytest.mark.parametrize('source,good,bad', [
    ('revenue no less than £22.6 million','>=£22.6m','£22.6m'),
    ('revenue not more than £2 million','<=£2m','£2m'),
    ('change (13.2)%','down 13.2%','13.2%'),
    ('improvement 28 per cent.','28%','82%'),
])
def test_quantity_aliases_preserve_bounds_and_signs(source,good,bad):
    norm = lambda s: _numeric_text(s)
    valid = lambda s: supported_numbers(norm(s),norm(source)) and bound_preserved(norm(s),norm(source))
    assert valid(good)
    assert not valid(bad)


def test_explicit_company_ticker_not_other_company_mentioned_in_release():
    text = 'GEO Exploration Limited\n10 September 2026\nGEO Exploration Limited (AIM: GEO) announces a placing. Greatland Resources (AIM: GGP) is mentioned as background.'
    assert extract_identity(text).ticker=='GEO'
    assert extract_identity('SIGMAROC PLC\n7 September 2026\n(EPIC: SRC / Market: AIM)').ticker=='SRC'
    assert extract_identity("National Grid plc ('National Grid' or 'Company')\n2 September 2026").company=='National Grid plc'
    assert extract_identity('Company plc\nAIM: ABC\nAIM: XYZ').ticker is None


def test_publisher_ai_summary_and_nested_layout_table_not_in_evaluation_source():
    html='<div id="ai-summary">AI SAYS FALSE NUMBER</div><div class="fr-view-element"><table><tr><td><p>16 September 2026</p><p>Example plc</p><table><tr><td><p>Full original paragraph.</p><p>Cash at year end is £1m; additional funding is required and there is no binding commitment in place.</p></td></tr></table></td></tr></table></div>'
    source=issuer_text(html)
    assert source.count('Full original paragraph.')==1
    assert '\n\n' in source and 'AI SAYS' not in source


def test_material_uncertainty_cannot_hide_in_citations_only():
    text='Example plc\n16 September 2026\nFinal results\nRevenue was £1m.\n\nGoing concern\nA material uncertainty exists which may cast significant doubt on the company as a going concern. Additional funding is not committed.'
    s=select_passages(text);rev='Revenue was £1m.';risk='A material uncertainty exists which may cast significant doubt on the company as a going concern. Additional funding is not committed.'
    c=CardDraft.model_validate({'announcement_type':'Results','headline':statement(s,'Example reports annual results',rev),
       'supporting_sentence':statement(s,rev,rev),'metrics':[], 'what_changed':None,'qualification':None})
    with pytest.raises(CardError) as e: check_card(text,s,c)
    assert 'GOING_CONCERN_OMITTED' in e.value.findings
    c.qualification=Statement.model_validate(statement(s,risk,risk))
    assert check_card(text,s,c)['status']=='passed'
    c.qualification=Statement.model_validate(statement(s,'Management expects further progress.',risk))
    with pytest.raises(CardError):check_card(text,s,c)


def test_no_material_uncertainty_does_not_force_a_false_warning():
    text='Example plc\n16 September 2026\nFinal results\nRevenue was £1m.\n\nGoing concern\nThere is no material uncertainty which may cast significant doubt on going concern.'
    s=select_passages(text);rev='Revenue was £1m.'
    c=CardDraft.model_validate({'announcement_type':'Results','headline':statement(s,'Example reports results',rev),'supporting_sentence':statement(s,rev,rev),'metrics':[],'what_changed':None,'qualification':None})
    assert check_card(text,s,c)['status']=='passed'


def test_all_validation_inputs_are_in_build_fingerprint():
    text=(Path(__file__).resolve().parents[2]/'rnsrepo/public_access.py').read_text()
    for name in ('rnsrepo/sections.py','rnsrepo/citations.py','rnsrepo/validation.py','rnsrepo/schema.py','product/paste.py'):
        assert repr(name) in text
