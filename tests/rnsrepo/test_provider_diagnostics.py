from types import SimpleNamespace
import json
from unittest.mock import patch
import pytest
from rnsrepo.extractor import _provider_error, CardExtractor
from product.paste import PasteRequest
from test_card import Client, TRT


@pytest.mark.parametrize('code', ['credit_balance_exhausted','organization_usage_limit_exceeded',
    'organization_spend_limit_exceeded','project_spend_limit_exceeded','insufficient_quota'])
def test_new_quota_errors_are_not_reported_as_transient_rate_limits(code, caplog):
    error=type('RateLimitError',(Exception,),{})("PRIVATE SOURCE SECRET")
    error.status_code=429;error.code=None
    error.body={'error':{'code':code,'type':'insufficient_quota','message':'PRIVATE SOURCE SECRET'}}
    client=Client(error=error)
    with pytest.raises(Exception,match='CARD_QUOTA') as e:
        CardExtractor('API-SECRET',client_factory=client.factory).extract(PasteRequest(text=TRT))
    assert e.value.telemetry['provider']['provider_code']==code
    assert len(client.calls)==1
    assert 'SECRET' not in caplog.text and 'SOURCE' not in caplog.text


def test_unknown_error_details_never_leave_provider_boundary():
    error=type('RateLimitError',(Exception,),{})("my-secret-org")
    error.status_code=429
    error.body={'code':'secret-user-text','type':'private-type'}
    error.response=SimpleNamespace(headers={'authorization':'secret-key','retry-after':'60','x-request-id':'secret-user'})
    safe=_provider_error(error)
    assert safe.code=='CARD_RATE_LIMIT'
    assert safe.provider_diagnostic=={'http_status':429,'provider_code':'unrecognised',
        'provider_type':'unrecognised','retry_after_seconds':60.0}
    assert 'secret' not in json.dumps(safe.provider_diagnostic)


def test_evaluation_stops_after_shared_quota_failure(tmp_path):
    from jobs.evaluate_rnsrepo import evaluate
    from rnsrepo.schema import CardError
    with patch('jobs.evaluate_rnsrepo.CardExtractor.extract',side_effect=CardError('CARD_QUOTA')) as extract:
        result=evaluate(live=True,models=('gpt-5-mini',),output=tmp_path/'result.json')
    assert extract.call_count==1
    assert result['results'][0]['status']=='CARD_QUOTA'
    assert len(result['results'])==10 and all(r['status']=='not_run' for r in result['results'][1:])
