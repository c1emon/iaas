"""Fake API acceptance lifecycle; no real PVE or guest qualification."""
from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from iaas.pve_template import acceptance as mod
from iaas.pve_template.acceptance_execution import begin
from iaas.pve_acceptance_contracts import canonical_digest, load_strict_json
from iaas.runtime_execution.execution import Execution, OperationFailed
from iaas.runtime_execution.outputs import TaskOutputs

FIXTURES = Path(__file__).resolve().parents[2] / 'docs/examples/pve-acceptance'
DIGEST = 'runtime@sha256:' + 'b' * 64


def request():
    value = load_strict_json(FIXTURES / 'acceptance-request.json')
    config = value['template_record']['configuration']
    config.update(template=1, smbios1='uuid=' + value['template_record']['smbios_uuid'],
                  scsi0='local-lvm:vm-9000-disk-0,size=8G', ide2='local-lvm:vm-9000-cloudinit,media=cdrom,size=4M',
                  cores=2, memory=2048, agent='1', net0='virtio,bridge=vmbr0', digest='source')
    record = value['template_record']
    value['template_record'] = mod.pve._record_from_config(
        {'version': 'template', 'target': value['target'], 'vmid': record['vmid'],
         'artifact_digest': record['artifact_digest']}, config, record['execution_id'])
    return value


def admission(value):
    return {'schema_version': 1, 'execution_id': 'accept-001',
            'plan_digest': canonical_digest(value).removeprefix('sha256:'), 'target': value['target'],
            'approved': True, 'consumption': {'reserved': True, 'reservation_id': 'r-1'},
            'pending': {'record_id': 'p-1'}, 'serialization': {'held': True, 'context_id': 'c-1'}}


class API:
    def __init__(self, value, fault=''):
        self.value, self.fault = value, fault
        self.source = deepcopy(value['template_record']['configuration'])
        self.clone = None
        self.calls = []
        self.state = 'stopped'
        self.volumes = []
        self.last_task = ''

    def request(self, method, path, fields=None, **kwargs):
        self.calls.append((method, path, fields, kwargs))
        if path.endswith('/access/permissions'):
            return {fields['path']: {'VM.Audit': 1, 'Datastore.Audit': 1, 'Datastore.AllocateSpace': 1}}
        if path.endswith('/cluster/resources'):
            return ([{'vmid': 9100, 'node': 'pve1'}] if self.clone is not None or self.fault == 'occupied' else []) + [{'vmid': 9000, 'node': 'pve1'}]
        if '/tasks/' in path:
            if self.fault == 'start-task-error' and self.last_task == 'start':
                return {'status': 'stopped', 'exitstatus': 'ERROR'}
            return {'status': 'stopped', 'exitstatus': 'OK'}
        if path.endswith('/9000/config'):
            if self.fault == 'source-change' and any('/clone' in call[1] for call in self.calls):
                return {**self.source, 'memory': 999}
            return deepcopy(self.source)
        if path.endswith('/clone'):
            if self.fault == 'clone-lost':
                raise OperationFailed('private raw response must not leak')
            self.clone = {**self.source, 'template': 0, 'digest': 'clone',
                          'smbios1': 'uuid=22222222-2222-4222-8222-222222222222',
                          'scsi0': 'local-lvm:vm-9100-disk-0,size=8G',
                          'ide2': 'local-lvm:vm-9100-cloudinit,media=cdrom,size=4M'}
            self.volumes = ['local-lvm:vm-9100-disk-0', 'local-lvm:vm-9100-cloudinit']
            return self.task('clone')
        if path.endswith('/content'):
            return [{'volid': value, 'vmid': 9100} for value in self.volumes]
        if path.endswith('/9100/config'):
            if method == 'PUT':
                self.clone.update({key: value for key, value in fields.items() if key not in {'delete', 'digest'}})
                for key in fields.get('delete', '').split(','):
                    self.clone.pop(key, None)
                return None
            if self.fault == 'identity-replaced' and self.state == 'running':
                return {**self.clone, 'smbios1': 'uuid=33333333-3333-4333-8333-333333333333'}
            return deepcopy(self.clone)
        if path.endswith('/status/start'):
            self.state = 'running'
            if self.fault == 'start-lost':
                raise OperationFailed('lost start')
            return self.task('start')
        if path.endswith('/agent/ping'):
            return {'result': {}}
        if path.endswith('/agent/exec'):
            assert json.loads(kwargs['body']) == {'command': ['cloud-init', 'status', '--format', 'json']}
            return {'pid': 123}
        if path.endswith('/agent/exec-status'):
            cloud = {'status': 'done', 'extended_status': 'done', 'errors': [], 'recoverable_errors': {}, 'boot_status_code': 'enabled-by-generator'}
            if self.fault == 'guest-failed':
                cloud['extended_status'] = 'degraded done'
            return {'exited': True, 'exitcode': 0, 'out-data': json.dumps(cloud)}
        if path.endswith('/agent/get-host-name'):
            return {'result': {'host-name': 'unchanged' if self.fault == 'hostname' else self.value['cloud_init']['hostname']}}
        if path.endswith('/status/current'):
            return {'status': self.state}
        if path.endswith('/status/stop'):
            self.state = 'stopped'
            return self.task('stop')
        if method == 'DELETE' and path.endswith('/9100'):
            if self.fault == 'delete-lost':
                self.clone = None
                raise OperationFailed('lost delete')
            self.clone = None
            if self.fault != 'volume-remains':
                self.volumes = []
            return self.task('delete')
        raise AssertionError((method, path))

    def task(self, phase):
        self.last_task = phase
        return f'UPID:pve1:00000001:00000001:00000001:{phase}:9100:root@pam:'


def execute(tmp_path, fault=''):
    value = request()
    journal = begin(tmp_path / 'original', 'accept', value, admission(value), 'accept-001', DIGEST)
    api = API(value, fault)
    result = mod.Acceptance(api, value, journal, tmp_path / 'original').execute()
    return result, journal, api


def test_full_lifecycle_checks_and_cleanup(tmp_path):
    result, journal, api = execute(tmp_path)
    assert result['overall'] == 'passed'
    assert all(item['status'] == 'passed' for item in result['checks'])
    assert result['cleanup']['snippets']['status'] == 'not_required'
    assert api.clone is None and api.volumes == []
    assert journal['vm_delete']['status'] == 'deleted'
    assert 'local-lvm:vm-9100-cloudinit' in journal['temporary_vm']['volumes']
    assert all('/9000/' not in path or path.endswith('/clone') for method, path, _, _ in api.calls if method != 'GET')
    assert 'accept-001' not in json.dumps(result['template'])


@pytest.mark.parametrize('fault,overall,delete', [
    ('guest-failed', 'failed', True), ('hostname', 'failed', True),
    ('source-change', 'failed', True), ('occupied', 'failed', False),
    ('clone-lost', 'unknown', False), ('start-lost', 'unknown', False),
    ('delete-lost', 'unknown', True), ('identity-replaced', 'unknown', False),
    ('start-task-error', 'failed', True), ('volume-remains', 'failed', True),
])
def test_failure_cleanup_and_unknown_boundaries(tmp_path, fault, overall, delete):
    result, journal, api = execute(tmp_path, fault)
    assert result['overall'] == overall
    assert any(method == 'DELETE' for method, *_ in api.calls) == delete
    assert 'private raw' not in json.dumps(result)
    if fault.endswith('lost'):
        assert journal['mutation_active'] is True


def test_runtime_observe_different_output_never_constructs_client(tmp_path, monkeypatch):
    value = request()
    api = API(value)
    monkeypatch.setattr(mod.pve, '_client', lambda *args: api)
    reqfile, admfile = tmp_path / 'request.json', tmp_path / 'admission.json'
    reqfile.write_text(json.dumps(value))
    admfile.write_text(json.dumps(admission(value)))
    selected = SimpleNamespace(options={'execution_mode': 'start'}, files={'acceptance_request': reqfile, 'execution_admission': admfile})
    outputs = TaskOutputs.create(tmp_path / 'start', Path(__file__).parents[2], [reqfile, admfile])
    mod.run(selected, 'accept', '', Execution(outputs, {}), DIGEST, 'accept-001')
    count = len(api.calls)
    monkeypatch.setattr(mod.pve, '_client', lambda *args: pytest.fail('observe attempted API'))
    selected.options = {'execution_mode': 'observe'}
    selected.files = {'original_execution_dir': tmp_path / 'start/diagnostics/execution', 'acceptance_request': reqfile}
    observed = TaskOutputs.create(tmp_path / 'observe', Path(__file__).parents[2], [reqfile])
    mod.run(selected, 'accept', '', Execution(observed, {}), DIGEST, 'accept-001')
    assert len(api.calls) == count
    assert json.loads((tmp_path / 'observe/diagnostics/result.json').read_text())['overall'] == 'passed'


def test_guest_timeout_uses_independent_cleanup_budget(tmp_path, monkeypatch):
    clock = SimpleNamespace(now=0.0)
    def sleep(seconds):
        clock.now += seconds
    monkeypatch.setattr(mod, 'time', SimpleNamespace(monotonic=lambda: clock.now, sleep=sleep))
    value = request()
    value['timeouts']['guest_seconds'] = 1
    api = API(value)
    original = api.request
    def call(method, path, **kwargs):
        if path.endswith('/agent/ping'):
            raise OperationFailed('not ready')
        return original(method, path, **kwargs)
    api.request = call
    journal = begin(tmp_path / 'original', 'accept', value, admission(value), 'accept-001', DIGEST)
    result = mod.Acceptance(api, value, journal, tmp_path / 'original').execute()
    assert result['overall'] == 'failed'
    assert result['failure_stage'] == 'guest_agent'
    assert result['cleanup']['vm']['status'] == 'passed'
    assert api.clone is None


def test_inherited_cloudinit_volume_is_never_adopted_or_deleted(tmp_path):
    value = request()
    api = API(value)
    original = api.request
    def call(method, path, **kwargs):
        result = original(method, path, **kwargs)
        if path.endswith('/clone'):
            api.clone['ide2'] = api.source['ide2']
        return result
    api.request = call
    journal = begin(tmp_path / 'original', 'accept', value, admission(value), 'accept-001', DIGEST)
    result = mod.Acceptance(api, value, journal, tmp_path / 'original').execute()
    assert result['overall'] == 'unknown'
    assert not any(method == 'DELETE' for method, *_ in api.calls)
    assert not result['residuals']['inventory_complete']


def test_disk_bound_rejected_before_clone(tmp_path):
    value = request()
    value['temporary_vm']['disk_limit_bytes'] = 1024
    api = API(value)
    journal = begin(tmp_path / 'original', 'accept', value, admission(value), 'accept-001', DIGEST)
    result = mod.Acceptance(api, value, journal, tmp_path / 'original').execute()
    assert result['overall'] == 'failed'
    assert not any(method != 'GET' for method, *_ in api.calls)


def test_cloudinit_residual_is_reported_even_if_system_disk_deleted(tmp_path):
    value = request()
    api = API(value, 'volume-remains')
    original = api.request
    def call(method, path, **kwargs):
        result = original(method, path, **kwargs)
        if method == 'DELETE':
            api.volumes = ['local-lvm:vm-9100-cloudinit']
        return result
    api.request = call
    journal = begin(tmp_path / 'original', 'accept', value, admission(value), 'accept-001', DIGEST)
    result = mod.Acceptance(api, value, journal, tmp_path / 'original').execute()
    assert result['overall'] == 'failed'
    assert result['cleanup']['vm']['status'] == 'passed'
    assert [x['identity'] for x in result['residuals']['items']] == ['local-lvm:vm-9100-cloudinit']


def test_metadata_volumes_count_against_disk_limit(tmp_path):
    value = request()
    value['temporary_vm']['disk_limit_bytes'] = 8 * 1024 ** 3
    api = API(value)
    journal = begin(tmp_path / 'original', 'accept', value, admission(value), 'accept-001', DIGEST)
    result = mod.Acceptance(api, value, journal, tmp_path / 'original').execute()
    assert result['overall'] == 'failed'
    assert not any(method != 'GET' for method, *_ in api.calls)
