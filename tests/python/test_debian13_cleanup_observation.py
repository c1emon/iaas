"""Known post-delete PVE 5xx reads must not replay the delete mutation."""
import pytest
from test_pve_template_acceptance import (
    API,
    DIGEST,
    Snippets,
    admission,
    begin,
    request,
)

from iaas.pve_template import acceptance as mod
from iaas.pve_template.responses import RequestOutcomeUnknown


@pytest.mark.parametrize('http_status,persistent,expected', [
    (500, False, 'passed'),
    (500, True, 'unknown'),
    (403, False, 'unknown'),
])
def test_cleanup_retries_only_bounded_read_queries(tmp_path, monkeypatch, http_status, persistent, expected):
    clock = [0.0]
    monkeypatch.setattr(mod.time, 'monotonic', lambda: clock[0])
    monkeypatch.setattr(mod.time, 'sleep', lambda seconds: clock.__setitem__(0, clock[0] + 10))
    value = request()

    class TransientInventoryAPI(API):
        cleanup_queries = 0

        def request(self, method, path, fields=None, **kwargs):
            if method == 'GET' and path.endswith('/content') and self.last_task == 'delete':
                self.cleanup_queries += 1
                if persistent or self.cleanup_queries == 1:
                    self.calls.append((method, path, fields, kwargs))
                    raise RequestOutcomeUnknown(http_status)
            return super().request(method, path, fields, **kwargs)

    api = TransientInventoryAPI(value)
    journal = begin(tmp_path / 'original', 'accept', value, admission(value), 'accept-001', DIGEST)
    result = mod.Acceptance(api, value, journal, tmp_path / 'original', Snippets(api)).execute()
    assert result['overall'] == expected
    assert sum(method == 'DELETE' for method, *_ in api.calls) == 1
    assert api.clone is None
    if expected == 'passed':
        assert api.cleanup_queries == 2
        assert journal['cleanup_inventory_retries'] == {'count': 1, 'last_http_status': 500}
        assert result['cleanup']['volumes']['status'] == 'passed'
    else:
        assert result['cleanup']['volumes']['status'] == 'unknown'
        assert api.cleanup_queries == (4 if persistent else 1)
