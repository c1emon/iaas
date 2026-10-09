"""Public error information survives capture without trusting raw tool text."""
import json
from pathlib import Path
import re
import sys

import pytest

from iaas.common.errors import Diagnostic, ValidationError
from iaas.common.public_diagnostics import MARKER, capture_diagnostics, exception_diagnostics, safe_diagnostics
from iaas.runtime_execution.execution import Execution, OperationFailed
from iaas.runtime_execution.outputs import TaskOutputs
from iaas.opnsense_workflow.save_diagnostics import public_failure_diagnostics


@pytest.mark.parametrize('code,status', [('authentication_failed', 401), ('permission_denied', 403),
                                        ('timeout', None), ('api_port_invalid', None)])
def test_safe_error_survives_real_subprocess_and_phase_summary(tmp_path, capfd, code, status):
    outputs = TaskOutputs.create(tmp_path / 'task', tmp_path / 'implementation', [])
    execution = Execution(outputs, {})
    entry = {'code': code, 'field': 'destination_port', 'status_code': status,
             'message': 'private-api-secret', 'invocation': {'password': 'private-password'}}
    script = f"print('private-config'); print({(MARKER + json.dumps(entry))!r}); raise SystemExit(2)"
    with pytest.raises(OperationFailed):
        execution.run('opnsense-workflow-save-filter-rules', [sys.executable, '-c', script], outputs.path('work'))
    summary = json.loads((outputs.root / 'summary.json').read_text())
    assert summary['diagnostics'][0]['code'] == code
    assert summary['diagnostics'][0]['field'] == 'destination_port'
    assert summary['phases'][0]['exit_code'] == 2
    assert not any(value in json.dumps(summary) for value in ('private-api-secret', 'private-password', 'private-config'))
    assert capfd.readouterr() == ('', '')
    assert 'private-config' in Path(summary['phases'][0]['capture']).read_text()


def test_warning_survives_success_and_errors_take_priority_over_warning_volume(tmp_path):
    outputs = TaskOutputs.create(tmp_path / 'task', tmp_path / 'implementation', [])
    execution = Execution(outputs, {})
    entry = {'code': 'protected_warning', 'warning_count': 2, 'message': 'private-warning'}
    execution.run('k3s-preflight', [sys.executable, '-c', f'print({(MARKER + json.dumps(entry))!r})'], outputs.path('work'))
    execution.finish({'component': 'k3s'})
    assert execution.diagnostics[0]['severity'] == 'warning'
    assert 'private-warning' not in json.dumps(execution.diagnostics)
    noisy = [{'code': 'protected_warning', 'warning_count': index + 1} for index in range(100)]
    assert safe_diagnostics(noisy + [{'code': 'permission_denied', 'status_code': 403}])[0]['code'] == 'permission_denied'


def test_untrusted_markers_and_attributes_cannot_leak_values(tmp_path):
    entries = [None, {'code': []}, {'code': 'private-token'},
               {'code': 'timeout', 'message': 'private-token', 'field': 'private-password',
                'action': 'private-action', 'status_code': True, 'exit_code': 9999}]
    assert safe_diagnostics(entries) == [{'code': 'timeout', 'severity': 'error', 'message': 'Operation timed out.'}]
    capture = tmp_path / 'capture'
    capture.write_text('private-raw\n' + MARKER + '{malformed}\n' + MARKER + json.dumps(entries[-1]) + '\n')
    assert capture_diagnostics(capture) == safe_diagnostics(entries)
    assert exception_diagnostics(ValidationError('private-token'))[0]['code'] == 'operation_failed'
    assert exception_diagnostics(ValidationError('private-token', diagnostic=Diagnostic('http_transport', 'http_failure', status_code=503)))[0]['status_code'] == 503


def test_opnsense_fields_and_backend_status_become_value_free_public_errors():
    entries = public_failure_diagnostics({'validation_details': [
        {'field': 'destination_port', 'reason': 'Please specify a valid portnumber, name, alias or range.'},
        {'field': 'source_port', 'reason': 'private-config'}],
        'http_status_codes': ['403'], 'timeout_reported': True}, 'filter-rules')
    assert {row['code'] for row in entries} == {'api_port_invalid', 'api_validation_failed', 'permission_denied', 'timeout'}
    assert entries[0]['field'] == 'destination_port'
    assert 'private-config' not in json.dumps(entries)


def test_runtime_cli_emits_phase_error_in_public_json(tmp_path, monkeypatch, capsys):
    import iaas.runtime_execution.__main__ as entrypoint
    from test_runtime_dispatch import config, REPO
    entry = config(tmp_path, 'pve', {'cluster': str(REPO / 'tests/fixtures/runtime/pve-cluster.yml'),
                                    'vms': str(REPO / 'tests/fixtures/runtime/vms.yml')})

    def fail(selected, operation, scope, execution, **kwargs):
        marker = MARKER + json.dumps({'code': 'permission_denied', 'status_code': 403, 'message': 'private-token'})
        execution.run('pve-health', [sys.executable, '-c', f"print({marker!r}); print('private-token'); raise SystemExit(17)"], execution.outputs.path('work'))

    monkeypatch.setattr(entrypoint, 'run_component', fail)
    output = tmp_path / 'result'
    assert entrypoint.main(['--environment', str(entry), '--component', 'pve', '--operation', 'health',
                           '--scope', 'synthetic-pve', '--output', str(output)]) == 17
    text = capsys.readouterr().out
    public = json.loads(text)
    assert public['diagnostics'][0]['code'] == 'permission_denied'
    assert public['diagnostics'][0]['status_code'] == 403
    assert public['phases'][0]['phase'] == 'pve-health'
    assert public['phases'][0]['exit_code'] == 17
    assert 'private-token' not in text


def test_launcher_and_runtime_share_the_same_public_message_contract():
    from iaas.common.public_diagnostics import MESSAGES
    source = (Path(__file__).resolve().parents[2] / 'automation/launcher/diagnostics.go').read_text()
    launcher = dict(re.findall(r'^\s*"([a-z0-9_]+)":\s*"([^"]*)",$', source, re.MULTILINE))
    assert launcher == MESSAGES
