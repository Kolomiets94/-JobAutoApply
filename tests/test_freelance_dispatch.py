from unittest.mock import Mock, patch
import freelancehunt_adapter as fh
from application_dispatcher import dispatch


def lead():
    return {'source':'freelancehunt','can_api_bid':True,'external_id':'123','title':'Вёрстка лендинга',
            'budget':{'amount':3000,'currency':'RUB'}}


def test_api_dispatch_and_confirmed_response(monkeypatch):
    monkeypatch.setenv('AUTO_FREELANCE_APPLY','1')
    monkeypatch.setenv('FREELANCEHUNT_TOKEN','test-token')
    comment = 'Hello\nСтоимость: 3000 RUB. Срок: 3 дн.'
    response = Mock(status_code=201, json=lambda:{'data':{'id':456,'attributes':{'comment':comment}}})
    with patch.object(fh.requests,'post',return_value=response) as post:
        assert dispatch(lead(),'Hello')['status'] == 'SUBMITTED'
    assert post.call_args.kwargs['json']['safe_type'] == 'employer'


def test_plain_http_success_is_not_counted_as_sent(monkeypatch):
    monkeypatch.setenv('AUTO_FREELANCE_APPLY','1')
    monkeypatch.setenv('FREELANCEHUNT_TOKEN','test-token')
    with patch.object(fh.requests,'post',return_value=Mock(status_code=200,json=lambda:{})):
        assert dispatch(lead(),'Hello')['status'] == 'NEEDS_CONFIRMATION'


def test_missing_token_is_explicit(monkeypatch):
    monkeypatch.setenv('AUTO_FREELANCE_APPLY','1')
    monkeypatch.delenv('FREELANCEHUNT_TOKEN',raising=False)
    assert dispatch(lead(),'Hello')['reason'] == 'freelancehunt_token_missing'
