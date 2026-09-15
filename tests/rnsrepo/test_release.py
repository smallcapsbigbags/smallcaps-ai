"""Production-discovered presentation aliases; no new numerical permissions."""
from pathlib import Path
import runpy
import pytest
from rnsrepo.schema import CardError
from rnsrepo.validation import check_card

FIXTURE = runpy.run_path(str(Path(__file__).with_name("test_card.py")))
draft, statement, TRT = (FIXTURE[k] for k in ("draft", "statement", "TRT"))


@pytest.mark.parametrize('duration', ['6-month', '6‑month', '6–month'])
def test_numeric_hyphenated_duration_is_not_a_new_unsupported_number(duration):
    s,c=draft()
    quote='The funded development programme lasts six months.'
    c.supporting_sentence=type(c.supporting_sentence).model_validate(statement(s,
        'Continental supports a funded ' + duration + ' development programme.',quote))
    assert check_card(TRT,s,c)['status']=='passed'
    c.supporting_sentence.text='Continental supports a funded 9-month development programme.'
    with pytest.raises(CardError):check_card(TRT,s,c)


def test_duration_in_headline_requires_its_own_support():
    s,c=draft()
    award='Transense has secured a development and supply contract with Continental.'
    duration='The funded development programme lasts six months.'
    c.headline=type(c.headline).model_validate(statement(s,
        'Continental funds a six-month development programme',award))
    with pytest.raises(CardError) as error:
        check_card(TRT,s,c)
    assert 'UNSUPPORTED_NUMBER' in error.value.findings
    c.headline=type(c.headline).model_validate(statement(s,
        'Continental funds a six-month development programme',award,duration))
    assert check_card(TRT,s,c)['status']=='passed'
