import pytest

from iaas.opnsense_workflow.reader import FixedCollectionTransport, _HttpFailure


@pytest.mark.parametrize('tables,rows,status,table', [
    (['OTHER'], [], 'unsupported', 'absent'),
    (['A'], [], 'unsupported', 'empty_or_unreadable'),
    (['A'], [{'ip': '192.0.2.10'}], 'unsupported', 'residual_nonempty'),
    ([''], [], 'unknown', 'unknown'),
    (None, [], 'unknown', 'unknown'),
])
def test_retirement_does_not_turn_absence_or_empty_response_into_completion(tables, rows, status, table):
    class Wire(FixedCollectionTransport):
        def __init__(self):
            self.calls = []

        def _request(self, method, path, payload=None):
            self.calls.append((method, path))
            return tables if path.endswith('/aliases') else {'rows': rows, 'total': len(rows)}

    wire = Wire()
    result = wire.active_check('aliases', ['A'], {'state': 'absent'})
    assert result['status'] == status
    assert result['coverage']['table'] == table
    assert result['coverage']['pf_states'] == 'not_touched'
    assert all(path.startswith('firewall/alias_util/') for _, path in wire.calls)


def test_retirement_unreadable_is_unknown():
    class Wire(FixedCollectionTransport):
        def _request(self, *args, **kwargs):
            raise _HttpFailure('failed', 'permission_denied')

    wire = Wire({'endpoint': 'https://192.0.2.1', 'ssl_verify': True}, {})
    result = wire.active_check('aliases', ['A'], {'state': 'absent'})
    assert result['status'] == 'unknown'
    assert result['reason'] == 'permission_denied'
