from copy import deepcopy

from iaas.opnsense_workflow.reader import FixedCollectionTransport, _HttpFailure


UUID = '11111111-1111-4111-8111-111111111111'
DESIRED = {'name': 'WEB', 'type': 'port', 'content': ['443'], 'state': 'present', 'enabled': True}
RULE = f'@1 pass in quick on igb0 inet proto tcp from any to any port 443 label "{UUID}"'


class Wire(FixedCollectionTransport):
    def __init__(self, *, version='26.7.3', denied=False, disabled=False):
        self.calls = []
        self.version = version
        self.denied = denied
        self.disabled = disabled

    def _request(self, method, path, payload=None):
        self.calls.append((method, path))
        if path == 'core/firmware/status':
            return {'product': {'product_version': self.version}}
        if path == 'firewall/filter/get':
            return {'filter': {'rules': {'rule': {UUID: {
                'enabled': '0' if self.disabled else '1', 'protocol': 'TCP',
                'source_port': '', 'destination_port': 'WEB',
            }}}}}
        if path == 'firewall/d_nat/get':
            return {'DNat': {'rule': {}}}
        if path == 'firewall/one_to_one/get':
            return {'filter': {'onetoone': {'rule': {}}}}
        if path == 'diagnostics/firewall/pf_statistics/rules':
            if self.denied:
                raise _HttpFailure('failed', 'permission_denied')
            return {'rules': {'filter rules': {RULE: {}}, 'nat rules': {}}}
        raise AssertionError(path)


def test_port_transport_reads_native_uuid_consumers_and_loaded_rules():
    wire = Wire()
    result = wire.active_check('aliases', ['WEB'], deepcopy(DESIRED))
    assert result['status'] == 'verified'
    assert result['matches'][0]['uuid'] == UUID
    assert all(method == 'GET' for method, _ in wire.calls)
    assert not any('/alias_util/list/' in path for _, path in wire.calls)


def test_port_transport_denied_or_unqualified_never_passes():
    wire = Wire(denied=True)
    result = wire.active_check('aliases', ['WEB'], deepcopy(DESIRED))
    assert result['status'] == 'unknown'
    assert result['reason'] == 'permission_denied'
    wire = Wire(version='26.1')
    assert wire.active_check('aliases', ['WEB'], deepcopy(DESIRED))['status'] == 'unsupported'
    assert wire.calls == [('GET', 'core/firmware/status')]


def test_disabled_port_consumer_does_not_require_loaded_rule():
    result = Wire(disabled=True).active_check('aliases', ['WEB'], deepcopy(DESIRED))
    assert result['status'] == 'not_applicable'
