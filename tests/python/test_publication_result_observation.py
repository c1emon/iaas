import copy
import json
from pathlib import Path

import pytest

from iaas.common.errors import ValidationError
from iaas.observation import EvidenceSink, ObservationBudget
from iaas.pve_template.contracts import validate_publication_result
from iaas.pve_template.responses import RequestOutcomeUnknown
from iaas.pve_template.runtime import _observe_original_tasks


UPID = 'UPID:pve1:1:2:3:qmcreate:9001:user@pam:'


@pytest.mark.parametrize('exitstatus', ['OK', 'unexpected status'])
def test_original_task_transient_read_keeps_fixed_upid_and_native_outcome(exitstatus):
    class Client:
        phase = 'cleanup'
        budget = ObservationBudget(3)
        sink = EvidenceSink()
        calls = []

        def request(self, method, path):
            self.calls.append((method, path))
            if len(self.calls) == 1:
                raise RequestOutcomeUnknown(503)
            return {'status': 'stopped', 'exitstatus': exitstatus}

    client = Client()
    result = _observe_original_tasks(client, {'events': [
        {'phase': 'create', 'status': 'submitted', 'upid': UPID}]}, 'pve1')
    assert result == {'create': exitstatus}
    assert len(client.calls) == 2 and client.calls[0] == client.calls[1]
    assert all(method == 'GET' for method, _ in client.calls)
    groups = client.sink.rows()
    assert groups[0]['terminal']['status'] == 'ready'
    if exitstatus != 'OK':
        assert groups[1]['terminal']['status'] == 'failed'
        assert groups[1]['terminal']['evidence']['exitstatus'] == exitstatus


def test_original_running_task_refuses_without_waiting_or_replaying():
    class Client:
        phase = 'cleanup'
        budget = ObservationBudget(3)
        sink = EvidenceSink()
        calls = 0

        def request(self, method, path):
            self.calls += 1
            return {'status': 'running'}

    client = Client()
    with pytest.raises(ValidationError, match='still active or unknown'):
        _observe_original_tasks(client, {'events': [
            {'phase': 'create', 'status': 'submitted', 'upid': UPID}]}, 'pve1')
    assert client.calls == 1
    assert client.sink.rows()[0]['terminal']['reason'] == 'original_task_active'


def documents():
    root = Path(__file__).parents[2] / 'docs/examples/image-publish'
    return (json.loads((root / 'pve-template-result.json').read_text()),
            json.loads((root / 'pve-template-preview.json').read_text()))


def test_current_publication_result_preserves_observation_binding():
    result, preview = documents()
    assert validate_publication_result(result, preview) == result


@pytest.mark.parametrize('field', ['deadlines', 'deadline_outcome', 'stop_diagnostics'])
def test_publication_result_requires_current_observation_fields(field):
    result, preview = documents()
    result.pop(field)
    with pytest.raises(ValidationError, match='incomplete'):
        validate_publication_result(result, preview)


@pytest.mark.parametrize('field,value', [
    ('deadlines', {'work_deadline_at': 'private sensitive string'}),
    ('deadline_outcome', {'phase': 'cleanup', 'status': 'not_exceeded'}),
    ('stop_diagnostics', {'stopping': 'private sensitive string'}),
    ('status', {'private': 'sensitive'}),
])
def test_publication_result_rejects_malformed_fields_without_echo(field, value):
    result, preview = documents()
    result[field] = value
    with pytest.raises(ValidationError) as error:
        validate_publication_result(result, preview)
    assert 'private' not in str(error.value) and 'sensitive' not in str(error.value)


def test_publication_result_deadline_drift_rejected():
    result, preview = documents()
    result['deadlines'] = copy.deepcopy(result['deadlines'])
    result['deadlines']['work_deadline_at'] = '2098-01-01T00:00:00Z'
    with pytest.raises(ValidationError, match='deadline binding'):
        validate_publication_result(result, preview)
