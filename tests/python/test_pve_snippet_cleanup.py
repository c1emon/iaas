from __future__ import annotations

from copy import deepcopy
import hashlib
import importlib.machinery
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from iaas.pve_acceptance_contracts import canonical_digest, validate_snippet_cleanup_request
from iaas.pve_snippet_cleanup.evidence import validate_original
from iaas.pve_snippet_cleanup.runtime import cleanup, initial_result, run
from iaas.pve_template.acceptance_execution import begin, save
from iaas.runtime_execution.execution import Execution, OperationFailed
from iaas.runtime_execution.outputs import TaskOutputs

ROOT = Path(__file__).resolve().parents[2]
EXAMPLES = ROOT / 'docs/examples/pve-acceptance'


def load(name):
    return json.loads((EXAMPLES / name).read_text())


def reference(root, name, value):
    path = root / name
    save(path, value)
    return {'path': name, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def admission(request, execution_id):
    return {'schema_version': 1, 'execution_id': execution_id, 'plan_digest': canonical_digest(request).removeprefix('sha256:'),
            'target': request['target'], 'deadlines': request['deadlines'], 'approved': True, 'consumption': {'reserved': True, 'reservation_id': 'r1'},
            'pending': {'record_id': 'p1'}, 'serialization': {'held': True, 'context_id': 'c1'}}


@pytest.fixture
def evidence(tmp_path):
    request = load('cleanup-acceptance-request.json')
    original = load('acceptance-request.json')
    vm = request['original_vm']
    original['temporary_vm'].update(node=vm['node'], vmid=vm['vmid'])
    original_id = request['original_execution_id']
    journal = begin(tmp_path / 'accept', 'accept', original, admission(original, original_id), original_id, 'sha256:' + 'f' * 64)
    task = request['deletion_evidence']['native_task']
    journal.update(temporary_vm=vm, vm_delete={'status': 'deleted', 'execution_id': original_id, **vm, 'upid': task},
                   snippets=[{**request['snippets'][0], 'vmid': vm['vmid'], 'uploaded': True}],
                   tasks=[{'phase': 'delete', 'status': 'succeeded', 'upid': task}], mutation_active=False)
    ref = reference(tmp_path, 'accept/journal.json', journal)
    request['acceptance_evidence'].update(request=reference(tmp_path, 'accept/request.json', original), journal=ref,
                                           request_digest=canonical_digest(original), result=None)
    request['deletion_evidence'].update(result=ref, vm_absence=ref)
    request['ownership_records'] = {'manifest': ref, 'upload': ref}
    return tmp_path, validate_snippet_cleanup_request(request)


class FakeHelper:
    def __init__(self, *, refs=(), vmids=(), complete=True, answers=None):
        self.refs, self.vmids, self.complete = list(refs), list(vmids), complete
        self.answers = answers or [{'status': 'deleted', 'reason_code': 'absence_confirmed'}]
        self.calls = []

    def inspect(self):
        return {'complete': self.complete, 'nodes': ['pve1', 'pve2'], 'local_node': 'pve1',
                'vmids': self.vmids, 'references': self.refs, 'reference_strategy': 'all_storage_aliases_by_filename'}

    def delete(self, snippet):
        self.calls.append(snippet['file_id'])
        answer = self.answers[len(self.calls) - 1]
        if isinstance(answer, Exception):
            raise answer
        return answer


def execute(request, helper, root):
    journal = {'mutation_active': False}
    result = cleanup(request, helper, initial_result(request, 'cleanup-1', 'sha256:' + 'f' * 64), journal, root)
    return result, journal


def test_acceptance_original_evidence_and_exact_cleanup(evidence):
    root, request = evidence
    validate_original(request, root)
    helper = FakeHelper()
    result, journal = execute(request, helper, root / 'cleanup')
    assert result['overall'] == 'passed'
    assert helper.calls == [request['snippets'][0]['file_id']]
    assert journal['mutation_active'] is False


@pytest.mark.parametrize('mutation', ['digest', 'uuid', 'authorization', 'vm_delete', 'upload', 'task', 'origin'])
def test_original_conflicts_fail_before_helper(evidence, mutation):
    root, request = evidence
    if mutation == 'digest':
        request['snippets'][0]['sha256'] = '1' * 64
    elif mutation == 'uuid':
        request['original_vm']['smbios_uuid'] = '33333333-3333-4333-8333-333333333333'
    elif mutation == 'origin':
        request['origin'] = 'deployment'
        request['delete_plan'] = {'metadata': request['ownership_records']['manifest']}
    else:
        refs = request['acceptance_evidence']
        original = json.loads((root / refs['request']['path']).read_text())
        journal = json.loads((root / refs['journal']['path']).read_text())
        if mutation == 'authorization':
            original['authorization']['delete_temporary_resources'] = False
            refs['request'] = reference(root, 'accept/request.json', original)
        elif mutation == 'vm_delete':
            journal['vm_delete']['status'] = 'unknown'
        elif mutation == 'upload':
            journal['snippets'][0]['uploaded'] = False
        elif mutation == 'task':
            journal['tasks'][0]['status'] = 'running'
        ref = reference(root, 'accept/journal.json', journal)
        refs['journal'] = ref
        request['deletion_evidence'].update(result=ref, vm_absence=ref)
        request['ownership_records'] = {'manifest': ref, 'upload': ref}
    with pytest.raises((ValueError, KeyError)):
        validate_original(request, root)


@pytest.mark.parametrize('kwargs,status', [({'complete': False}, 'unknown'), ({'vmids': [9100]}, 'mismatch'),
    ({'refs': ['accept-001.yaml']}, 'referenced')])
def test_global_scope_and_references_prevent_deletion(evidence, kwargs, status):
    root, request = evidence
    helper = FakeHelper(**kwargs)
    result, _ = execute(request, helper, root / 'cleanup')
    assert result['items'][0]['status'] == status
    assert result['overall'] != 'passed' and not helper.calls


def test_absent_is_idempotent_and_ssh_timeout_stays_unknown(evidence):
    root, request = evidence
    result, journal = execute(request, FakeHelper(answers=[{'status': 'already_absent', 'reason_code': 'exact_target_absent'}]), root / 'one')
    assert result['overall'] == 'passed' and journal['mutation_active'] is False
    result, journal = execute(request, FakeHelper(answers=[TimeoutError()]), root / 'two')
    assert result['overall'] == 'unknown' and journal['mutation_active'] is True


def test_retry_preserves_full_list_and_requires_inactive_original(evidence):
    root, request = evidence
    old = deepcopy(request)
    journal = begin(root / 'prior', 'snippet-cleanup', old, admission(old, 'cleanup-0'), 'cleanup-0', 'sha256:' + 'f' * 64)
    refs = {'execution_id': 'cleanup-0', 'request_digest': canonical_digest(old),
            'request': reference(root, 'prior/request.json', old),
            'journal': reference(root, 'prior/journal.json', journal), 'result': None}
    request.update(retry_of='cleanup-0', retry_materials=refs, timeout_seconds=30,
                   deadlines={'work_deadline_at': '2031-01-01T00:00:00Z',
                              'cleanup_deadline_at': '2031-01-01T00:05:00Z'})
    validate_original(request, root)
    request['snippets'][0]['record_ref'] = 'different'
    with pytest.raises(ValueError):
        validate_original(request, root)
    request['snippets'] = old['snippets']
    journal['mutation_active'] = True
    refs['journal'] = reference(root, 'prior/journal.json', journal)
    with pytest.raises(ValueError):
        validate_original(request, root)


def test_start_then_observe_without_mutation(evidence, monkeypatch):
    root, request = evidence
    files = {'snippet_cleanup_request': root / 'cleanup-request.json', 'cleanup_evidence_dir': root,
             'execution_admission': root / 'admission.json'}
    save(files['snippet_cleanup_request'], request)
    save(files['execution_admission'], admission(request, 'cleanup-1'))
    helper = FakeHelper()
    monkeypatch.setattr('iaas.pve_snippet_cleanup.runtime.Helper', lambda *_, **kwargs: helper)
    output = root / 'output'
    output.mkdir()
    execution = Execution(TaskOutputs(output), {})
    run(SimpleNamespace(files=files, options={'execution_mode': 'start'}), 'snippet-cleanup', '', execution, 'sha256:' + 'f' * 64, 'cleanup-1')
    assert len(helper.calls) == 1
    observed = root / 'observed'
    observed.mkdir()
    run(SimpleNamespace(files={'original_execution_dir': output / 'diagnostics/execution'}, options={'execution_mode': 'observe'}),
        'snippet-cleanup', '', Execution(TaskOutputs(observed), {}), 'sha256:' + 'f' * 64, 'cleanup-1')
    assert len(helper.calls) == 1
    assert json.loads((observed / 'pve-snippet-cleanup-result.json').read_text())['overall'] == 'passed'


@pytest.fixture
def node_helper():
    loader = importlib.machinery.SourceFileLoader('snippet_delete_test', str(ROOT / 'automation/pve-node/bin/iaas-pve-snippet-delete'))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


def test_exact_helper_digest_symlink_absence(node_helper, tmp_path, monkeypatch):
    directory = tmp_path / 'snippets'
    directory.mkdir()
    path = directory / 'test-100-user-data.yml'
    path.write_bytes(b'private-content')
    monkeypatch.setattr(node_helper.subprocess, 'run', lambda *a, **k: SimpleNamespace(stdout=str(path)))
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    assert node_helper.delete_exact('local', path.name, '0' * 64, node_helper.Deadline('2099-01-01T00:00:00Z'))[0] == 'mismatch'
    assert path.exists()
    assert node_helper.delete_exact('local', path.name, digest, node_helper.Deadline('2099-01-01T00:00:00Z'))[0] == 'deleted'
    assert node_helper.delete_exact('local', path.name, digest, node_helper.Deadline('2099-01-01T00:00:00Z'))[0] == 'already_absent'
    path.symlink_to(directory / 'other.yml')
    assert node_helper.delete_exact('local', path.name, digest, node_helper.Deadline('2099-01-01T00:00:00Z'))[0] == 'mismatch'
    assert node_helper.delete_exact('local', '../unsafe.yml', digest, node_helper.Deadline('2099-01-01T00:00:00Z'))[0] == 'mismatch'


def test_pmxcfs_scans_shared_pending_snapshot_and_rejects_incomplete(node_helper, tmp_path):
    (tmp_path / '.members').write_text(json.dumps({'cluster': {'quorate': 1}}))
    (tmp_path / '.vmlist').write_text(json.dumps({'ids': {'200': {'node': 'pve2', 'type': 'qemu'}}}))
    for node in ('pve1', 'pve2'):
        for kind in ('qemu-server', 'lxc'):
            (tmp_path / 'nodes' / node / kind).mkdir(parents=True)
    (tmp_path / 'local').symlink_to(tmp_path / 'nodes/pve1')
    config = tmp_path / 'nodes/pve2/qemu-server/200.conf'
    config.write_text('[PENDING]\ncicustom: user=shared:snippets/pending.yaml\n[snap1]\ncicustom: user=alias:snippets/snapshot.yaml\n')
    scan = node_helper.inspect_cluster(tmp_path)
    assert scan['complete'] and scan['references'] == ['pending.yaml', 'snapshot.yaml']
    config.unlink()
    assert not node_helper.inspect_cluster(tmp_path)['complete']


def test_partial_cleanup_preserves_completed_facts(evidence):
    root, request = evidence
    second = {**request['snippets'][0], 'file_name': 'second.yaml', 'file_id': 'local:snippets/second.yaml', 'record_ref': 'second.yaml'}
    request['snippets'].append(second)
    helper = FakeHelper(answers=[{'status': 'deleted', 'reason_code': 'absence_confirmed'}, TimeoutError()])
    result, journal = execute(request, helper, root / 'cleanup')
    assert [item['status'] for item in result['items']] == ['deleted', 'unknown']
    assert result['overall'] == 'unknown' and len(result['residuals']['items']) == 1
    assert journal['mutation_active'] is True


def test_observe_missing_core_is_non_success_and_zero_mutation(tmp_path, monkeypatch):
    output = tmp_path / 'output'
    output.mkdir()
    monkeypatch.setattr('iaas.pve_snippet_cleanup.runtime.Helper', lambda *_: pytest.fail('observe created helper'))
    with pytest.raises(OperationFailed):
        run(SimpleNamespace(files={'original_execution_dir': tmp_path / 'missing'}, options={'execution_mode': 'observe'}),
            'snippet-cleanup', '', Execution(TaskOutputs(output), {}), 'sha256:' + 'f' * 64, 'cleanup-1')
    assert json.loads((output / 'summary.json').read_text())['status'] == 'unknown'


def test_observe_directory_overlap_refused(evidence):
    root, request = evidence
    original = root / 'prior'
    begin(original, 'snippet-cleanup', request, admission(request, 'cleanup-1'), 'cleanup-1', 'sha256:' + 'f' * 64)
    with pytest.raises(ValueError, match='overlap'):
        run(SimpleNamespace(files={'original_execution_dir': original}, options={'execution_mode': 'observe'}),
            'snippet-cleanup', '', Execution(TaskOutputs(original), {}), 'sha256:' + 'f' * 64, 'cleanup-1')


def test_helper_uses_admitted_ssh_target_not_ambient_environment(tmp_path):
    from iaas.pve_snippet_cleanup.runtime import Helper
    key, hosts = tmp_path / 'key', tmp_path / 'known_hosts'
    key.write_text('isolated-test-key')
    hosts.write_text('isolated-test-host-trust')
    key.chmod(0o600)
    hosts.chmod(0o600)
    selected = SimpleNamespace(files={'ssh_key': key, 'known_hosts': hosts})
    execution = SimpleNamespace(environ={'PVE_SSH_HOST': 'wrong.example.invalid', 'PVE_SSH_USER': 'wrong', 'PVE_SSH_PORT': '2222'})
    fixed = {'host': 'pve.example.invalid', 'user': 'automation', 'port': 22}
    helper = Helper(selected, execution, 30, fixed)
    assert helper.command[-1] == 'automation@pve.example.invalid'
    assert helper.command[-3:-1] == ['-p', '22']
    assert 'StrictHostKeyChecking=yes' in helper.command and 'IdentityAgent=none' in helper.command


def test_observe_corrupt_original_request_reports_unknown(tmp_path, monkeypatch):
    original, output = tmp_path / 'original', tmp_path / 'output'
    original.mkdir()
    output.mkdir()
    (original / 'request.json').write_text('{broken')
    monkeypatch.setattr('iaas.pve_snippet_cleanup.runtime.Helper', lambda *_: pytest.fail('observe created helper'))
    with pytest.raises(OperationFailed):
        run(SimpleNamespace(files={'original_execution_dir': original}, options={'execution_mode': 'observe'}),
            'snippet-cleanup', '', Execution(TaskOutputs(output), {}), 'sha256:' + 'f' * 64, 'cleanup-1')
    assert json.loads((output / 'summary.json').read_text())['status'] == 'unknown'


def test_helper_permission_denied_is_not_absence(node_helper, monkeypatch):
    def denied(*args, **kwargs):
        raise PermissionError('synthetic permission failure')
    monkeypatch.setattr(node_helper.subprocess, 'run', denied)
    assert node_helper.delete_exact('local', 'vm-9100.yaml', 'a' * 64, node_helper.Deadline('2099-01-01T00:00:00Z')) == ('failed', 'permission_denied')
    monkeypatch.setattr(node_helper.Path, 'read_text', denied)
    assert node_helper.inspect_cluster()['complete'] is False


def frozen_clock(monkeypatch, request):
    from iaas.pve_acceptance_contracts import deadline_timestamp
    from iaas.pve_template.deadlines import DeadlineBudget
    clock = {'utc': deadline_timestamp(request['deadlines']['work_deadline_at']) - 10, 'mono': 50.0}
    monkeypatch.setattr('iaas.pve_template.deadlines.time.time', lambda: clock['utc'])
    monkeypatch.setattr('iaas.pve_template.deadlines.time.monotonic', lambda: clock['mono'])
    return clock, DeadlineBudget(request['deadlines'])


def test_cleanup_expired_admission_records_no_write_and_unknown_resources(evidence, monkeypatch):
    root, request = evidence
    request['deadlines'] = {'work_deadline_at': '2000-01-01T00:00:00Z',
                            'cleanup_deadline_at': '2000-01-01T00:01:00Z'}
    files = {'snippet_cleanup_request': root / 'expired-request.json', 'cleanup_evidence_dir': root,
             'execution_admission': root / 'expired-admission.json'}
    save(files['snippet_cleanup_request'], request)
    save(files['execution_admission'], admission(request, 'cleanup-expired'))
    monkeypatch.setattr('iaas.pve_snippet_cleanup.runtime.Helper', lambda *a, **k: pytest.fail('expired start created helper'))
    monkeypatch.setattr('iaas.pve_snippet_cleanup.runtime.validate_original', lambda *a: pytest.fail('expired start read inventory'))
    output = root / 'expired-output'
    output.mkdir()
    with pytest.raises(OperationFailed):
        run(SimpleNamespace(files=files, options={'execution_mode': 'start'}), 'snippet-cleanup', '',
            Execution(TaskOutputs(output), {}), 'sha256:' + 'f' * 64, 'cleanup-expired')
    result = json.loads((output / 'pve-snippet-cleanup-result.json').read_text())
    assert result['deadline_outcome'] == {'phase': 'admission', 'status': 'rejected'}
    assert result['facility_writes'] == 'none' and result['overall'] == 'unknown'
    assert result['items'][0]['status'] == 'unknown' and not result['scope_check']['inventory_complete']
    original = output / 'diagnostics/execution'
    observed = root / 'expired-observed'
    observed.mkdir()
    monkeypatch.setattr('iaas.pve_snippet_cleanup.runtime.DeadlineBudget', lambda *a: pytest.fail('observe refreshed budget'))
    with pytest.raises(OperationFailed):
        run(SimpleNamespace(files={'original_execution_dir': original}, options={'execution_mode': 'observe'}),
            'snippet-cleanup', '', Execution(TaskOutputs(observed), {}), 'sha256:' + 'f' * 64, 'cleanup-expired')
    assert json.loads((observed / 'pve-snippet-cleanup-result.json').read_text()) == result


def test_cleanup_delayed_inventory_cannot_start_delete(evidence, monkeypatch):
    root, request = evidence
    clock, budget = frozen_clock(monkeypatch, request)
    helper = FakeHelper()
    inspect = helper.inspect
    def delayed():
        snapshot = inspect()
        clock['mono'] = budget.bounds['work']
        return snapshot
    helper.inspect = delayed
    result = cleanup(request, helper, initial_result(request, 'cleanup-late', 'sha256:' + 'f' * 64),
                     {'mutation_active': False, 'facility_writes': 'none'}, root / 'late', budget)
    assert not helper.calls
    assert helper.phase == 'work'
    assert result['deadline_outcome'] == {'phase': 'work', 'status': 'exceeded'}
    assert result['scope_check']['reason_code'] == 'work_deadline_expired'
    assert result['facility_writes'] == 'none' and result['overall'] == 'unknown'


def test_cleanup_cutoff_preserves_completed_items_and_stops_next_write(evidence, monkeypatch):
    root, request = evidence
    second = {**request['snippets'][0], 'file_name': 'second.yaml',
              'file_id': 'local:snippets/second.yaml', 'record_ref': 'second.yaml'}
    request['snippets'].append(second)
    clock, budget = frozen_clock(monkeypatch, request)
    helper = FakeHelper()
    delete = helper.delete
    def delayed(snippet):
        assert helper.phase == 'cleanup'
        answer = delete(snippet)
        clock['mono'] = budget.bounds['cleanup']
        return answer
    helper.delete = delayed
    journal = {'mutation_active': False, 'facility_writes': 'none'}
    result = cleanup(request, helper, initial_result(request, 'cleanup-cutoff', 'sha256:' + 'f' * 64),
                     journal, root / 'cutoff', budget)
    assert len(helper.calls) == 1
    assert [item['status'] for item in result['items']] == ['deleted', 'unknown']
    assert result['deadline_outcome'] == {'phase': 'cleanup', 'status': 'exceeded'}
    assert result['facility_writes'] == 'issued' and journal['mutation_active'] is False


def test_cleanup_relative_timeout_after_intent_is_zero_send_not_deadline(evidence, monkeypatch):
    root, request = evidence
    request['timeout_seconds'] = 1
    clock, budget = frozen_clock(monkeypatch, request)
    helper = FakeHelper()
    original_save = save
    def delayed_save(path, value):
        original_save(path, value)
        if path.name == 'journal.json' and value.get('mutation_active') is True:
            clock['mono'] = budget.local['cleanup']
    monkeypatch.setattr('iaas.pve_snippet_cleanup.runtime.save', delayed_save)
    journal = {'mutation_active': False, 'facility_writes': 'none'}
    result = cleanup(request, helper, initial_result(request, 'cleanup-relative', 'sha256:' + 'f' * 64),
                     journal, root / 'relative', budget)
    assert not helper.calls
    assert result['deadline_outcome'] == {'phase': None, 'status': 'not_exceeded'}
    assert result['items'][0]['reason_code'] == 'cleanup_timeout'
    assert result['facility_writes'] == 'none' and journal['mutation_active'] is False
