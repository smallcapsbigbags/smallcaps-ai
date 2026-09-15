"""Citation IDs remove transcription errors without relaxing factual checks."""
import json
from pathlib import Path
import pytest
from product.paste import PasteRequest
from rnsrepo.citations import citation_catalog, wire_schema, resolve_wire
from rnsrepo.extractor import request_kwargs
from rnsrepo.schema import CardError
from rnsrepo.sections import select_passages
from rnsrepo.validation import check_card
from test_card import TRT, draft, response


def test_wire_resolves_exact_source_and_passes_existing_checks():
    selection, card = draft()
    catalog=citation_catalog(selection)
    wire=response(card)['output'][0]['content'][0]['text']
    resolved=resolve_wire(wire,catalog)
    checked=check_card(TRT,selection,resolved)
    for anchor in checked['anchors']:
        assert TRT[anchor['start']:anchor['end']]==anchor['quote']
    assert resolved.metrics[2].value=='>£0.7m'
    assert wire_schema(catalog)['$defs']['Reference']['enum']==list(catalog)
    assert all(c.quote in TRT for c in catalog.values())

@pytest.mark.parametrize('bad', ['q99999', {'passage_id':'p0','quote':'invented quotation'}])
def test_unknown_or_recopied_evidence_is_rejected(bad):
    selection,card=draft();catalog=citation_catalog(selection)
    wire=json.loads(response(card)['output'][0]['content'][0]['text'])
    wire['metrics'][2]['evidence']=[bad]
    with pytest.raises(CardError,match='CARD_FORMAT'):resolve_wire(json.dumps(wire),catalog)


def test_ids_do_not_allow_wrong_numbers_or_lost_conditions():
    selection,card=draft();catalog=citation_catalog(selection)
    wire=json.loads(response(card)['output'][0]['content'][0]['text'])
    wire['metrics'][2]['value']='>£7m'
    with pytest.raises(CardError) as e:check_card(TRT,selection,resolve_wire(json.dumps(wire),catalog))
    assert 'UNSUPPORTED_NUMBER' in e.value.findings
    wire['metrics'][2]['value']='>£0.7m';wire['metrics'][2]['note']=''
    with pytest.raises(CardError) as e:check_card(TRT,selection,resolve_wire(json.dumps(wire),catalog))
    assert 'CONDITION_LOST' in e.value.findings


def test_complete_trt_source_uses_bounded_ids_not_model_copied_quotes():
    path=Path(__file__).resolve().parents[2]/'benchmarks/rnsrepo/trt-supplied-announcement.txt'
    source=path.read_text();kwargs,sel=request_kwargs(PasteRequest(text=source),'gpt-5-mini')
    packet=json.loads(kwargs['input']);catalog=citation_catalog(sel)
    assert packet['excerpts'] and 'passages' not in packet
    assert len(json.dumps(kwargs,ensure_ascii=False).encode())<30000
    for c in catalog.values():assert c.quote in source and 12<=len(c.quote)<=900
    assert any('more than £0.7m' in c.quote for c in catalog.values())
    assert any('Following successful completion' in c.quote for c in catalog.values())


def test_short_table_unit_survives_as_verbatim_context():
    source="Financial Highlights\n\n£000\n\nRevenue 2026 243699\n\nAdjusted profit 12900\n"
    selection=select_passages(source)
    catalog=citation_catalog(selection)
    assert any('£000' in c.quote for c in catalog.values())
    for c in catalog.values(): assert c.quote in source
