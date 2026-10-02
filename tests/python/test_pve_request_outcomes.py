"""Native permission rejection is distinct from an unresolved HTTP response."""
from urllib.error import HTTPError

import pytest

from iaas.pve_template.runtime import PveHttpsClient
from iaas.pve_template.responses import RequestOutcomeUnknown, RequestRejected


@pytest.mark.parametrize('status,server,reason,expected', [
    (403, 'pve-api-daemon/3.0', 'Permission check failed (/vms/798, VM.GuestAgent.Unrestricted)', RequestRejected),
    (403, 'gateway', 'Permission check failed (/vms/798, VM.GuestAgent.Unrestricted)', RequestOutcomeUnknown),
    (403, 'pve-api-daemon/3.0', 'Forbidden secret', RequestOutcomeUnknown),
    (403, 'pve-api-daemon/3.0', 'Permission check failed (/vms/799, VM.GuestAgent.Unrestricted)', RequestOutcomeUnknown),
    (500, 'pve-api-daemon/3.0', 'Permission check failed (/vms/798, VM.GuestAgent.Unrestricted)', RequestOutcomeUnknown),
])
def test_https_permission_outcome(status, server, reason, expected):
    client = PveHttpsClient('https://pve.example.invalid:8006', 'private-token')
    path = '/api2/json/nodes/pve1/qemu/798/agent/exec'

    class Opener:
        def open(self, request, **kwargs):
            raise HTTPError(request.full_url, status, reason, {'Server': server}, None)

    client.opener = Opener()
    with pytest.raises(expected) as caught:
        client.request('POST', path)
    assert caught.value.http_status == status
    assert 'private-token' not in str(caught.value)
    assert 'secret' not in str(caught.value)
