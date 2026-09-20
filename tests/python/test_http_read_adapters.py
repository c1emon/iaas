"""The two domain adapters retain their public failure and request contracts."""
import pytest
import requests

from iaas_automation.opnsense_diagnostics import adapter as diagnostics
from iaas_automation.opnsense_workflow import reader as workflow


class Response:
    def __init__(self, status=200, error=None):
        self.status_code = status
        self.error = error
        self.closed = False

    def iter_content(self, size):
        if self.error is not None:
            raise self.error
        yield b'{}'

    def close(self):
        self.closed = True


class Session:
    def __init__(self, responses):
        self.responses = responses
        self.calls = []

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        return self.responses[len(self.calls) - 1]

    def close(self):
        pass


@pytest.fixture(params=['workflow', 'diagnostics'])
def adapter(request, monkeypatch):
    def create(responses):
        session = Session(responses)
        if request.param == 'workflow':
            client = workflow.FixedCollectionTransport(
                {'endpoint': 'https://firewall.example', 'ssl_verify': False},
                {'OPNSENSE_API_KEY': 'test-key', 'OPNSENSE_API_SECRET': 'test-secret'}, session=session)
            return lambda: client._request('GET', 'firewall/alias/get'), session, workflow
        monkeypatch.setattr(diagnostics.requests, 'Session', lambda: session)
        client = diagnostics.Transport('https://firewall.example', 'test-key', 'test-secret', verify=False)
        return lambda: client.call('aliases', {'current': 1}), session, diagnostics
    return create


@pytest.mark.parametrize('status,reason', [(401, 'authentication_failed'), (404, 'endpoint_unavailable'), (500, 'http_failure')])
def test_http_failures_close_response_and_keep_domain_reason(adapter, status, reason):
    response = Response(status)
    call, session, domain = adapter([response])
    with pytest.raises(Exception) as caught:
        call()
    assert caught.value.reason == reason
    assert caught.value.status == ('unsupported' if status == 404 else ('failed' if domain is workflow else 'error'))
    assert response.closed
    assert len(session.calls) == 1


def test_stream_failure_is_safe_and_closes_response(adapter):
    response = Response(error=requests.ConnectionError('private-backend-token'))
    call, session, _ = adapter([response])
    with pytest.raises(Exception) as caught:
        call()
    assert caught.value.reason == 'transport_failure'
    assert 'private-backend-token' not in str(caught.value)
    assert response.closed
    assert len(session.calls) == 1


def test_cumulative_budget_survives_multiple_calls_and_tls_is_preserved(adapter, monkeypatch):
    responses = [Response(), Response()]
    call, session, domain = adapter(responses)
    monkeypatch.setattr(domain, 'MAX_TOTAL_BYTES', 3)
    assert call() == {}
    with pytest.raises(Exception) as caught:
        call()
    assert caught.value.reason == 'response_bound_exceeded'
    assert caught.value.status == 'unsupported'
    assert all(response.closed for response in responses)
    assert len(session.calls) == 2
    for _, _, kwargs in session.calls:
        assert kwargs['verify'] is False
        assert kwargs['allow_redirects'] is False
        assert kwargs['stream'] is True
        assert kwargs['timeout'] == (5, 15)
