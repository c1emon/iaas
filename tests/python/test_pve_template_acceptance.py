"""Fake API acceptance lifecycle; no real PVE or guest qualification."""
from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from iaas.pve_template import acceptance as mod
from iaas.pve_template.acceptance_execution import begin as _begin
from iaas.pve_template.acceptance_plan import build_preview
from iaas.pve_acceptance_contracts import canonical_digest, load_strict_json
from iaas.runtime_execution.execution import Execution, OperationFailed
from iaas.runtime_execution.outputs import TaskOutputs
from test_pve_acceptance_execution import PlannedAdmission

FIXTURES = Path(__file__).resolve().parents[2] / 'docs/examples/pve-acceptance'
DIGEST = 'runtime@sha256:' + 'b' * 64


@pytest.fixture(autouse=True)
def bounded_test_cleanup(monkeypatch):
    original = mod.Acceptance.cleanup
    def bounded(self):
        if getattr(self.client, 'fault', '') == 'volume-remains':
            self.budget.limit('cleanup', .1)
        return original(self)
    monkeypatch.setattr(mod.Acceptance, 'cleanup', bounded)


def request():
    value = load_strict_json(FIXTURES / 'acceptance-request.json')
    value['runtime'] = {'image_digest': DIGEST}
    config = value['template_record']['configuration']
    config.update(template=1, smbios1='uuid=' + value['template_record']['smbios_uuid'],
                  scsi0='local-lvm:vm-9000-disk-0,size=8G', ide2='local-lvm:vm-9000-cloudinit,media=cdrom,size=4M',
                  cores=2, memory=2048, agent='1', net0='virtio,bridge=vmbr0', digest='source')
    record = value['template_record']
    value['template_record'] = mod.pve._record_from_config(
        {'version': 'template', 'target': value['target'], 'vmid': record['vmid'], 'cluster_scope': 'fixture-cluster',
         'artifact_digest': record['artifact_digest']}, config, record['execution_id'])
    return value


def preview(value):
    return build_preview(value, {'readiness': {'status': 'ready'}}, image_digest=value['runtime']['image_digest'])


def begin(root, operation, value, admitted, execution_id, image_digest):
    return _begin(root, operation, value, admitted, execution_id, image_digest, preview=admitted.preview)


def admission(value, planned=None):
    planned = preview(value) if planned is None else planned
    return PlannedAdmission({'schema_version': 2, 'execution_id': 'accept-001',
            'plan_digest': planned['preview_digest'].removeprefix('sha256:'),
            'request_digest': canonical_digest(value), 'runtime': value['runtime'],
            'vmid_reservation': {'cluster_scope': value['cluster_scope'], 'vmids': [value['temporary_vm']['vmid']],
                                 'reservation_id': 'r-1', 'context_id': 'c-1'},
            'target': value['target'], 'deadlines': value['deadlines'],
            'approved': True, 'consumption': {'reserved': True, 'reservation_id': 'r-1'},
            'pending': {'record_id': 'p-1'}, 'serialization': {'held': True, 'context_id': 'c-1'}}, planned)


class Snippets:
    def __init__(self, api=None):
        self.api = api

    def capabilities(self, helper):
        return {'schema_version': 'helper-capabilities/v1', 'helper': helper, 'protocol_version': 2,
                'capabilities': {name: True for name in ('acceptance', 'create_only', 'verify', 'inspect', 'exact_delete', 'reference', 'digest', 'deadline')}}

    def inspect(self):
        vmids = [9000]
        if self.api is not None and (self.api.clone is not None or self.api.fault == 'occupied'):
            vmids.append(9100)
        return {'complete': True, 'local_node': 'pve1', 'nodes': ['pve1'], 'vmids': vmids,
                'references': [], 'reference_strategy': 'all_storage_aliases_by_filename'}

    def upload(self, snippet, content):
        import yaml
        data = yaml.safe_load(content)
        assert 'user' not in data and isinstance(data['users'], list)

    def delete(self, snippet):
        return {'schema_version': 1, 'status': 'deleted', 'reason_code': 'deleted'}


def test_template_user_is_preserved_without_deprecated_scalar(tmp_path):
    import yaml
    value = request()
    value['template_record']['configuration']['ciuser'] = 'debian'
    api = API(value)
    journal = begin(tmp_path / 'original', 'accept', value, admission(value), 'accept-001', DIGEST)
    data = yaml.safe_load(mod.acceptance_snippets.user_data(value))
    assert data['users'] == [{'name': 'debian', 'lock_passwd': True}]
    assert 'user' not in data
    result = mod.Acceptance(api, value, journal, tmp_path / 'original', Snippets()).execute()
    assert result['overall'] == 'passed'
    assert api.source['ciuser'] == 'debian'
    assert journal['snippets'][0]['uploaded'] is True
    assert journal['snippets'][0]['cleanup']['status'] == 'deleted'


@pytest.mark.parametrize('fault', ['upload', 'referenced', 'delete'])
def test_snippet_failure_never_reports_success(tmp_path, fault):
    class Broken(Snippets):
        inspections = 0

        def upload(self, snippet, content):
            if fault == 'upload':
                raise TimeoutError('unknown remote outcome')

        def inspect(self):
            self.inspections += 1
            snapshot = super().inspect()
            if fault == 'referenced' and journal.get('snippets'):
                snapshot['references'] = [journal['snippets'][0]['file_name']]
            return snapshot

        def delete(self, snippet):
            assert fault != 'referenced'
            raise TimeoutError('unknown remote outcome')

    value = request()
    api = API(value)
    journal = begin(tmp_path / 'original', 'accept', value, admission(value), 'accept-001', DIGEST)
    result = mod.Acceptance(api, value, journal, tmp_path / 'original', Broken()).execute()
    assert result['overall'] == 'unknown'
    assert result['cleanup']['snippets']['status'] == 'unknown'
    assert any(x['kind'] == 'snippet' for x in result['residuals']['items'])
    if fault == 'upload':
        assert not any(p.endswith('/status/start') for _, p, _, _ in api.calls)


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
            from iaas.pve_template.admission import ACCEPTANCE_PRIVILEGES
            return {fields['path']: {name: 1 for name in (*ACCEPTANCE_PRIVILEGES, 'VM.Clone',
                                    'Sys.Audit', 'SDN.Use', 'Datastore.Audit', 'Datastore.AllocateSpace')}}
        if '/pools/' in path:
            return {'members': ([{'vmid': 9100, 'type': 'qemu', 'node': 'pve1'}] if self.clone is not None else [])}
        if path.endswith('/cluster/status'):
            return [{'type': 'node', 'name': 'pve1', 'online': 1}]
        if path.endswith('/nodes/pve1/status'):
            return {'cpuinfo': {'cpus': 16}, 'memory': {'total': 64 * 1024 ** 3}}
        if '/storage/' in path and path.endswith('/status'):
            return {'enabled': 1, 'active': 1, 'type': 'dir', 'content': 'images,snippets', 'avail': 1024 ** 4}
        if path.endswith('/network'):
            return [{'iface': self.value['temporary_vm']['bridge'], 'type': 'bridge', 'active': 1, 'bridge_vlan_aware': 1}]
        if path.endswith('/cluster/resources'):
            return ([{'vmid': 9100, 'node': 'pve1', 'type': 'qemu', 'pool': self.value['temporary_vm']['pool']}]
                    if self.clone is not None or self.fault == 'occupied' else []) + [{'vmid': 9000, 'node': 'pve1', 'type': 'qemu'}]
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
            self.clone = {**self.source, 'template': 0, 'digest': 'clone', 'description': fields['description'],
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
    result = mod.Acceptance(api, value, journal, tmp_path / 'original', Snippets(api)).execute()
    return result, journal, api


def test_full_lifecycle_checks_and_cleanup(tmp_path):
    result, journal, api = execute(tmp_path)
    assert result['overall'] == 'passed'
    assert all(item['status'] == 'passed' for item in result['checks'])
    assert result['cleanup']['snippets']['status'] == 'passed'
    assert api.clone is None and api.volumes == []
    assert journal['vm_delete']['status'] == 'deleted'
    assert 'local-lvm:vm-9100-cloudinit' in journal['temporary_vm']['volumes']
    assert all('/9000/' not in path or path.endswith('/clone') for method, path, _, _ in api.calls if method != 'GET')
    assert 'accept-001' not in json.dumps(result['template'])
    clone = next(fields for method, path, fields, _ in api.calls if method == 'POST' and path.endswith('/clone'))
    assert clone['pool'] == 'acceptance'
    assert not any('/pools/' in path for method, path, _, _ in api.calls if method != 'GET')


@pytest.mark.parametrize('when', ['before_start', 'cleanup'])
def test_pool_movement_prevents_dependent_writes(tmp_path, when):
    value = request()
    api = API(value)
    original = api.request
    configured = False

    def call(method, path, **kwargs):
        nonlocal configured
        rows = original(method, path, **kwargs)
        if method == 'PUT' and path.endswith('/9100/config'):
            configured = True
        moved = (configured if when == 'before_start' else api.state == 'running')
        if path.endswith('/cluster/resources') and moved:
            for row in rows:
                if row['vmid'] == 9100:
                    row['pool'] = 'other'
        return rows

    api.request = call
    journal = begin(tmp_path / 'original', 'accept', value, admission(value), 'accept-001', DIGEST)
    result = mod.Acceptance(api, value, journal, tmp_path / 'original', Snippets(api)).execute()
    assert result['overall'] != 'passed'
    assert not any(method == 'DELETE' for method, *_ in api.calls)
    if when == 'before_start':
        assert not any(path.endswith('/status/start') for _, path, _, _ in api.calls)


@pytest.mark.parametrize('fault,overall,delete', [
    ('guest-failed', 'failed', True), ('hostname', 'failed', True),
    ('source-change', 'failed', True), ('occupied', 'unknown', False),
    ('clone-lost', 'unknown', False), ('start-lost', 'unknown', False),
    ('delete-lost', 'unknown', True), ('identity-replaced', 'unknown', False),
    ('start-task-error', 'failed', True), ('volume-remains', 'unknown', True),
])
def test_failure_cleanup_and_unknown_boundaries(tmp_path, fault, overall, delete):
    result, journal, api = execute(tmp_path, fault)
    assert result['overall'] == overall
    assert any(method == 'DELETE' for method, *_ in api.calls) == delete
    assert 'private raw' not in json.dumps(result)
    if fault.endswith('lost'):
        assert journal['mutation_active'] is True


def test_cleanup_only_failure_has_stopping_diagnostics(tmp_path):
    result, _, _ = execute(tmp_path, 'delete-lost')
    assert all(row['status'] == 'passed' for row in result['checks'])
    assert result['stop_diagnostics']['stopping']['phase'] == 'cleanup'
    assert result['stop_diagnostics']['stopping']['status'] == 'unknown'


def test_runtime_observe_different_output_never_constructs_client(tmp_path, monkeypatch):
    value = request()
    api = API(value)
    monkeypatch.setattr(mod.pve, '_client', lambda *args: api)
    monkeypatch.setattr(mod.acceptance_snippets, 'Snippets', lambda *args, **kwargs: Snippets())
    reqfile, admfile, prevfile = tmp_path / 'request.json', tmp_path / 'admission.json', tmp_path / 'preview.json'
    reqfile.write_text(json.dumps(value))
    admitted = admission(value)
    admfile.write_text(json.dumps(admitted))
    prevfile.write_text(json.dumps(admitted.preview))
    selected = SimpleNamespace(options={'execution_mode': 'start'}, files={'acceptance_request': reqfile, 'execution_admission': admfile,
                                                                         'acceptance_preview': prevfile})
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
    from iaas.pve_template import deadlines
    monkeypatch.setattr(deadlines.time, 'monotonic', lambda: clock.now)
    value = request()
    value['timeouts']['guest_seconds'] = 1
    api = API(value)
    original = api.request
    def call(method, path, **kwargs):
        if path.endswith('/agent/ping'):
            from iaas.pve_template.responses import RequestOutcomeUnknown
            raise RequestOutcomeUnknown(503)
        return original(method, path, **kwargs)
    api.request = call
    journal = begin(tmp_path / 'original', 'accept', value, admission(value), 'accept-001', DIGEST)
    result = mod.Acceptance(api, value, journal, tmp_path / 'original', Snippets()).execute()
    assert result['overall'] == 'unknown'
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
    result = mod.Acceptance(api, value, journal, tmp_path / 'original', Snippets()).execute()
    assert result['overall'] == 'unknown'
    assert not any(method == 'DELETE' for method, *_ in api.calls)
    assert not result['residuals']['inventory_complete']


@pytest.mark.parametrize('operation', ['exec', 'ping'])
def test_authoritative_guest_rejection_allows_owned_cleanup(tmp_path, operation):
    value = request()
    api = API(value)
    original = api.request

    def call(method, path, **kwargs):
        if path.endswith('/agent/' + operation):
            raise mod.RequestRejected(method, path)
        return original(method, path, **kwargs)

    api.request = call
    journal = begin(tmp_path / 'original', 'accept', value, admission(value), 'accept-001', DIGEST)
    result = mod.Acceptance(api, value, journal, tmp_path / 'original', Snippets()).execute()
    assert result['overall'] == 'failed'
    assert result['facility_writes'] == 'issued'
    assert result['cleanup']['vm']['status'] == 'passed'
    assert journal['mutation_active'] is False
    if operation == 'exec':
        rejected = next(item for item in journal['tasks'] if item['phase'] == 'guest_exec')
        assert (rejected['status'], rejected['http_status']) == ('rejected', 403)


def test_guest_rejection_preserves_another_unknown_request(tmp_path):
    value = request()
    api = API(value)
    original = api.request
    journal = begin(tmp_path / 'original', 'accept', value, admission(value), 'accept-001', DIGEST)

    def call(method, path, **kwargs):
        if path.endswith('/agent/ping'):
            journal['tasks'].append({'phase': 'other', 'status': 'unknown'})
            journal.update(mutation_active=True, facility_writes='unknown')
        if path.endswith('/agent/exec'):
            raise mod.RequestRejected(method, path)
        return original(method, path, **kwargs)

    api.request = call
    result = mod.Acceptance(api, value, journal, tmp_path / 'original', Snippets()).execute()
    assert result['overall'] == 'unknown'
    assert result['facility_writes'] == 'unknown'
    assert not any(method == 'DELETE' for method, *_ in api.calls)


def test_disk_bound_rejected_before_clone(tmp_path):
    value = request()
    value['temporary_vm']['disk_limit_bytes'] = 1024
    api = API(value)
    journal = begin(tmp_path / 'original', 'accept', value, admission(value), 'accept-001', DIGEST)
    result = mod.Acceptance(api, value, journal, tmp_path / 'original', Snippets()).execute()
    assert result['overall'] == 'unknown'
    checks = {item['id']: item for item in result['checks']}
    assert checks['full_clone']['reason_code'] == 'disk_limit_exceeded'
    assert checks['source_unchanged']['reason_code'] == 'source_snapshot_missing'
    assert result['failure_stage'] == 'full_clone'
    assert not any(method != 'GET' for method, *_ in api.calls)


@pytest.mark.parametrize('fault,reason,status', [
    ('changed', 'source_changed', 'failed'),
    ('query', 'unclassified_query_error', 'unknown'),
    ('shape', 'source_evidence_insufficient', 'unknown'),
])
def test_source_recheck_diagnostics(tmp_path, fault, reason, status):
    value = request()
    api = API(value)
    original = api.request
    reads = 0

    def call(method, path, **kwargs):
        nonlocal reads
        if path.endswith('/9000/config'):
            reads += 1
            if reads > 1:
                if fault == 'query':
                    raise TimeoutError('private transport detail')
                if fault == 'shape':
                    return []
                return {**api.source, 'memory': 999}
        return original(method, path, **kwargs)

    api.request = call
    journal = begin(tmp_path / 'original', 'accept', value, admission(value), 'accept-001', DIGEST)
    result = mod.Acceptance(api, value, journal, tmp_path / 'original', Snippets()).execute()
    source = next(item for item in result['checks'] if item['id'] == 'source_unchanged')
    assert (source['status'], source['reason_code']) == (status, reason)
    assert 'private transport detail' not in json.dumps(result)


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
    result = mod.Acceptance(api, value, journal, tmp_path / 'original', Snippets()).execute()
    assert result['overall'] == 'unknown'
    assert result['cleanup']['vm']['status'] == 'passed'
    assert [x['identity'] for x in result['residuals']['items'] if x['kind'] == 'volume'] == ['local-lvm:vm-9100-cloudinit']


def test_metadata_volumes_count_against_disk_limit(tmp_path):
    value = request()
    value['temporary_vm']['disk_limit_bytes'] = 8 * 1024 ** 3
    api = API(value)
    journal = begin(tmp_path / 'original', 'accept', value, admission(value), 'accept-001', DIGEST)
    result = mod.Acceptance(api, value, journal, tmp_path / 'original', Snippets()).execute()
    assert result['overall'] == 'unknown'
    assert not any(method != 'GET' for method, *_ in api.calls)


@pytest.mark.parametrize('fault', ['', 'missing', 'duplicate', 'wrong-owner', 'invalid-size', 'over-limit'])
def test_missing_config_size_requires_exact_storage_evidence(tmp_path, fault):
    value = request()
    value['template_record']['configuration']['ide2'] = 'local-lvm:vm-9000-cloudinit,media=cdrom'
    if fault == 'over-limit':
        value['temporary_vm']['disk_limit_bytes'] = 8 * 1024 ** 3
    api = API(value)
    original = api.request

    def call(method, path, **kwargs):
        result = original(method, path, **kwargs)
        if path.endswith('/content'):
            source = {'volid': 'local-lvm:vm-9000-cloudinit', 'vmid': 9000, 'size': 4 * 1024 ** 2}
            if fault == 'wrong-owner':
                source['vmid'] = 9001
            if fault == 'invalid-size':
                source['size'] = True
            result = [] if fault == 'missing' else [source] * (2 if fault == 'duplicate' else 1)
            result += [{'volid': vol, 'vmid': 9100, 'size': 4 * 1024 ** 2} for vol in api.volumes]
        if method == 'GET' and path.endswith('/9100/config'):
            result['ide2'] = 'local-lvm:vm-9100-cloudinit,media=cdrom'
        return result

    api.request = call
    journal = begin(tmp_path / 'original', 'accept', value, admission(value), 'accept-001', DIGEST)
    result = mod.Acceptance(api, value, journal, tmp_path / 'original', Snippets()).execute()
    assert result['overall'] == ('unknown' if fault else 'passed')
    if fault:
        assert not any(method != 'GET' for method, *_ in api.calls)


def test_task_pool_content_and_exec_status_converge_without_replaying_writes(tmp_path):
    from iaas.pve_template.responses import RequestOutcomeUnknown
    value = request()
    api = API(value)
    original = api.request
    counts = {}
    def delayed(method, path, **kwargs):
        result = original(method, path, **kwargs)
        key = 'task' if '/tasks/' in path else 'pool' if path.endswith('/cluster/resources') and api.clone else 'content' if path.endswith('/content') and api.clone else 'exec' if path.endswith('/agent/exec-status') else None
        if key:
            counts[key] = counts.get(key, 0) + 1
            if counts[key] == 1:
                if key == 'task':
                    return {'status': 'stopped'}
                if key == 'pool':
                    return [{**r, 'pool': None} if r.get('vmid') == 9100 else r for r in result]
                if key == 'content':
                    return result[:1]
                raise RequestOutcomeUnknown(503)
        return result
    api.request = delayed
    journal = begin(tmp_path / 'original', 'accept', value, admission(value), 'accept-001', DIGEST)
    result = mod.Acceptance(api, value, journal, tmp_path / 'original', Snippets()).execute()
    assert result['overall'] == 'passed'
    assert journal['clone_candidate']['complete'] is True
    assert journal['clone_candidate']['clone_marker'] == journal['preview']['clone_marker']
    assert all(counts[key] >= 2 for key in ('task', 'pool', 'content', 'exec'))
    assert sum(path.endswith('/clone') for method, path, *_ in api.calls if method == 'POST') == 1
    assert sum(path.endswith('/agent/exec') for method, path, *_ in api.calls if method == 'POST') == 1
    assert {row['check'] for row in result['stop_diagnostics']['observations']} >= {'native_task', 'clone_content', 'exec_status'}


def test_failed_claim_keeps_both_volume_owners_after_cleanup_and_source_checks(tmp_path):
    value = request()
    api = API(value)
    original = api.request
    def conflict(method, path, **kwargs):
        result = original(method, path, **kwargs)
        if path.endswith('/content') and api.clone:
            return [{**row, 'vmid': 999} for row in result]
        return result
    api.request = conflict
    journal = begin(tmp_path / 'original', 'accept', value, admission(value), 'accept-001', DIGEST)
    result = mod.Acceptance(api, value, journal, tmp_path / 'original', Snippets()).execute()
    assert result['overall'] == 'unknown'
    assert journal.get('temporary_vm') is None
    assert result['stop_diagnostics']['recovery']['disposition'] == 'needs_evidence'
    assert journal['clone_candidate']['complete'] is True
    group = next(row for row in result['stop_diagnostics']['observations'] if row['check'] == 'clone_content')
    assert group['terminal']['status'] == 'failed'
    assert {row['volid'] for row in group['terminal']['evidence']['volumes']} == set(api.volumes)
    assert {row['vmid'] for row in group['terminal']['evidence']['volumes']} == {999}
    assert group['terminal']['observed_at']
    assert not any(method == 'DELETE' for method, *_ in api.calls)


def test_partial_candidate_waits_for_complete_uuid_and_expected_slots(tmp_path):
    value = request()
    api = API(value)
    original = api.request
    samples = []
    def partial(method, path, **kwargs):
        result = original(method, path, **kwargs)
        if method == 'GET' and path.endswith('/9100/config') and not samples:
            samples.append(True)
            result.pop('smbios1')
            result.pop('ide2')
        return result
    api.request = partial
    journal = begin(tmp_path / 'original', 'accept', value, admission(value), 'accept-001', DIGEST)
    result = mod.Acceptance(api, value, journal, tmp_path / 'original', Snippets()).execute()
    assert result['overall'] == 'passed'
    assert journal['clone_candidate']['complete'] is True
    group = next(g for g in result['stop_diagnostics']['observations'] if g['check'] == 'clone_candidate')
    assert group['terminal']['attempt'] == 2
    assert len(journal['clone_candidate']['slots']) == 2


def test_illegal_configuration_fails_immediately_with_safe_decision(tmp_path):
    value = request()
    api = API(value)
    original = api.request
    def invalid(method, path, **kwargs):
        result = original(method, path, **kwargs)
        if method == 'PUT' and path.endswith('/9100/config'):
            api.clone['cores'] = 'invalid'
        return result
    api.request = invalid
    journal = begin(tmp_path / 'original', 'accept', value, admission(value), 'accept-001', DIGEST)
    result = mod.Acceptance(api, value, journal, tmp_path / 'original', Snippets()).execute()
    group = next(g for g in result['stop_diagnostics']['observations'] if g['check'] == 'configuration')
    assert group['terminal']['status'] == 'failed'
    assert group['terminal']['reason'] == 'configuration_invalid'
    assert group['terminal']['attempt'] == 1
    assert not any(path.endswith('/status/start') for _, path, *_ in api.calls)
