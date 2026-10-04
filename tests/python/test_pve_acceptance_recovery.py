"""Software-only recovery cleanup/observation; no fixture authorizes real VM798."""
from copy import deepcopy
import json

import pytest

from iaas.pve_acceptance_contracts import canonical_digest
from iaas.pve_template import recovery
from iaas.pve_template.recovery_contracts import build_recovery_preview
from iaas.pve_template.recovery_evidence import reconcile_original
from test_pve_acceptance_recovery_evidence import API as ReadAPI, fixture, VOLUMES, SNIPPET, ORIGINAL, CALLER

ID = 'fixture-recovery-1'


class API(ReadAPI):
    def __init__(self):
        super().__init__()
        self.present = True
        self.state = 'running'
        self.volumes = set(VOLUMES)
        self.lost = False
        self.vm_deleted = False
        self.new_calls = []
    def request(self, method, path, *, fields=None):
        if method != 'GET':
            self.new_calls.append((method, path, fields))
            assert method == 'DELETE' or (method == 'POST' and path.endswith('/status/stop'))
            assert '/agent/' not in path and '/clone' not in path and not path.endswith('/status/start')
            if self.lost:
                raise TimeoutError('response unavailable')
            if path.endswith('/status/stop'):
                self.state = 'stopped'
            elif path.endswith('/qemu/798'):
                self.present = False
                self.vm_deleted = True
                # Model API preserving one exact original orphan disk.
                self.volumes.discard(VOLUMES[1])
            else:
                from urllib.parse import unquote
                volume = unquote(path.rsplit('/', 1)[1])
                self.volumes.discard(volume)
            return 'UPID:cohe:00000001:00000001:00000009:qmstop:798:root@pam:'
        if path.endswith('/cluster/resources'):
            return ([{'vmid': 798, 'node': 'cohe', 'type': 'qemu', 'pool': 'existing-old-pool'}] if self.present else []) + [{'vmid': 9004, 'node': 'cohe', 'type': 'qemu'}]
        if path.endswith('/status/current'):
            return {'status': self.state}
        if path.endswith('/content'):
            return [{'volid': v, 'vmid': 798} for v in sorted(self.volumes)]
        return super().request(method, path, fields=fields)


class Snippets:
    def __init__(self, api):
        self.api = api
        self.present = True
        self.deletes = []
        self.conflict = False
    def inspect(self):
        return {'complete': True, 'local_node': 'cohe', 'nodes': ['cohe'],
                'vmids': ([798] if self.api.present else []) + [9004], 'references': [SNIPPET.rsplit('/', 1)[1]] if self.api.present else [],
                'volume_references': [{'node': 'cohe', 'vmid': 9004, 'volid': VOLUMES[0]}] if self.conflict else [],
                'snippet_references': [{'node': 'cohe', 'vmid': 798, 'file_name': SNIPPET.rsplit('/', 1)[1]}] if self.api.present else []}
    def inspect_file(self, snippet):
        assert snippet['storage'] == 'local'
        assert snippet['file_name'] == SNIPPET.rsplit('/', 1)[1]
        return {'existence': 'present' if self.present else 'absent', 'sha256': snippet['sha256'] if self.present else None}
    def delete(self, snippet):
        assert not self.api.present and not self.api.volumes
        self.deletes.append(deepcopy(snippet))
        self.present = False
        return {'status': 'deleted'}


def setup(tmp_path):
    request, original, evidence, trust = fixture(tmp_path)
    api = API()
    snippets = Snippets(api)
    reconciliation = reconcile_original(request, original, evidence, api, snippets, trusted_rejection_exports=trust)
    preview = build_recovery_preview(request, reconciliation)
    admission = {'schema_version': 2, 'execution_id': ID,
                 'plan_digest': preview['preview_digest'].removeprefix('sha256:'), 'request_digest': canonical_digest(request),
                 'runtime': request['runtime'], 'target': request['target'], 'deadlines': request['deadlines'], 'approved': True,
                 'consumption': {'reserved': True, 'reservation_id': 'new-reservation'},
                 'pending': {'record_id': 'new-pending', 'execution_id': CALLER},
                 'serialization': {'held': True, 'context_id': 'new-context'}, 'recovery_of': ORIGINAL,
                 'vmid_reservation': {'cluster_scope': request['cluster_scope'], 'vmids': [798],
                                      'reservation_id': 'new-reservation', 'context_id': 'new-context'}}
    return request, preview, admission, original, evidence, api, snippets


def invoke(tmp_path, data):
    request, preview, admission, original, evidence, api, snippets = data
    return recovery.start(tmp_path / 'new', request, preview, admission, ID, request['runtime']['image_digest'], original, evidence, api, snippets)


def test_clean_full_owned_resources_and_preserve_original_pool_and_evidence(tmp_path):
    data = setup(tmp_path)
    original = data[3]
    before = {p: p.read_bytes() for p in original.iterdir()}
    result = invoke(tmp_path, data)
    assert result['overall'] == 'passed'
    assert result['original_acceptance'] == 'unknown'
    assert result['original_facility_writes'] == 'issued'
    assert result['facility_writes'] == 'issued'
    assert len(result['resources']) == 4
    assert all(row['existence'] == 'absent' for row in result['resources'])
    assert result['residuals'] == []
    assert all(p.read_bytes() == content for p, content in before.items())
    api, snippets = data[-2:]
    assert len(api.new_calls) == 3
    assert all('/pools/' not in path and '/access/' not in path for _, path, _ in api.new_calls)
    assert snippets.deletes[0]['created_by'] == ORIGINAL
    journal, observed = recovery.observe(tmp_path / 'new', ID)
    assert observed == result
    assert journal['mutation_active'] is False
    with pytest.raises(FileExistsError):
        invoke(tmp_path, data)


def test_response_loss_is_unknown_and_no_dependent_cleanup_or_restart(tmp_path):
    data = setup(tmp_path)
    data[-2].lost = True
    result = invoke(tmp_path, data)
    assert result['overall'] == 'unknown'
    assert result['facility_writes'] == 'unknown'
    assert len(data[-2].new_calls) == 1
    assert data[-1].deletes == []
    assert recovery.observe(tmp_path / 'new', ID)[1] == result
    with pytest.raises(FileExistsError):
        invoke(tmp_path, data)


def test_vm_already_absent_does_not_invent_old_deletion_success(tmp_path):
    data = setup(tmp_path)
    data[-2].present = False
    result = invoke(tmp_path, data)
    assert result['overall'] == 'passed'
    vm = result['resources'][0]
    assert vm['status'] == 'already_absent'
    assert vm['reason_code'] == 'current_absence_observed'
    assert all(not path.endswith('/qemu/798') and not path.endswith('/status/stop') for _, path, _ in data[-2].new_calls)
    assert result['original_acceptance'] == 'unknown'


@pytest.mark.parametrize('fault', ['uuid', 'reference', 'original_activity'])
def test_unsafe_ownership_or_activity_refuses_writes(tmp_path, fault):
    data = setup(tmp_path)
    api = data[-2]
    if fault == 'reference':
        data[-1].conflict = True
    elif fault == 'original_activity':
        api.active = True
    else:
        original = api.request
        def request(method, path, **kwargs):
            response = original(method, path, **kwargs)
            if path.endswith('/qemu/798/config'):
                response['smbios1'] = 'uuid=33333333-3333-4333-8333-333333333333'
            return response
        api.request = request
    result = invoke(tmp_path, data)
    assert result['overall'] == 'unknown'
    assert result['facility_writes'] == 'none'
    assert api.new_calls == []
    assert data[-1].deletes == []


def test_observe_has_no_budget_and_handles_missing_result(tmp_path, monkeypatch):
    data = setup(tmp_path)
    result = invoke(tmp_path, data)
    monkeypatch.setattr(recovery, 'DeadlineBudget', lambda *args: pytest.fail('observe cannot construct budgets'))
    assert recovery.observe(tmp_path / 'new', ID)[1] == result
    (tmp_path / 'new/result.json').unlink()
    assert recovery.observe(tmp_path / 'new', ID)[1] is None


def test_new_cutoff_expired_rejects_before_new_writes(tmp_path):
    data = list(setup(tmp_path))
    request, preview, admission = data[:3]
    request['deadlines'] = {'work_deadline_at': '2026-09-29T00:00:00Z', 'cleanup_deadline_at': '2026-09-29T00:10:00Z'}
    preview = build_recovery_preview(request, preview['reconciliation'])
    admission.update(deadlines=request['deadlines'], request_digest=canonical_digest(request), plan_digest=preview['preview_digest'].removeprefix('sha256:'))
    data[:3] = [request, preview, admission]
    result = invoke(tmp_path, data)
    assert result['overall'] == 'failed'
    assert result['facility_writes'] == 'none'
    assert result['deadline_outcome'] == {'phase': 'admission', 'status': 'rejected'}
    assert data[-2].new_calls == []


def test_reviewed_new_approval_can_clean_without_reconstructing_historical_trace(tmp_path):
    from test_pve_acceptance_recovery_evidence import write
    data = list(setup(tmp_path))
    request, _, admission, original, evidence, api, snippets = data
    caller = json.loads((evidence / 'caller.json').read_text())
    caller.pop('dispatches')
    request['caller_association']['material'] = write(evidence, 'caller.json', caller)
    request['rejection_evidence'] = []
    facts = reconcile_original(request, original, evidence, api, snippets)
    assert facts['original_activity'] == 'unknown'
    assert facts['disposition'] == 'administrator_decision'
    preview = build_recovery_preview(request, facts)
    admission.update(request_digest=canonical_digest(request), plan_digest=preview['preview_digest'].removeprefix('sha256:'))
    data[:3] = [request, preview, admission]
    result = invoke(tmp_path, data)
    assert result['overall'] == 'passed'
    assert result['original_activity'] == 'unknown'
    assert result['original_facility_writes'] == 'unknown'
    assert result['original_acceptance'] == 'unknown'
    assert result['facility_writes'] == 'issued'


def test_complete_helper_references_allow_pool_filtered_api_inventory(tmp_path):
    data = setup(tmp_path)
    api = data[-2]
    original_request = api.request
    def filtered(method, path, **kwargs):
        rows = original_request(method, path, **kwargs)
        if path.endswith('/cluster/resources'):
            return [row for row in rows if row['vmid'] == 798]
        return rows
    api.request = filtered
    assert invoke(tmp_path, data)['overall'] == 'passed'


def test_absent_resources_do_not_require_unused_mutation_privileges(tmp_path):
    data = setup(tmp_path)
    api, snippets = data[-2:]
    api.present = False
    api.volumes.clear()
    snippets.present = False
    original_request = api.request
    def readonly_permissions(method, path, **kwargs):
        if path.endswith('/access/permissions'):
            return {kwargs['fields']['path']: {'VM.Audit': 0, 'Datastore.Audit': 0}}
        return original_request(method, path, **kwargs)
    api.request = readonly_permissions
    assert invoke(tmp_path, data)['overall'] == 'passed'
    assert api.new_calls == []


def test_later_new_authority_retains_complete_original_list_and_previous_recovery(tmp_path):
    from test_pve_acceptance_recovery_evidence import write
    data = setup(tmp_path)
    first = invoke(tmp_path, data)
    request, _, _, original, evidence, api, snippets = data
    refs = {}
    for name in ('request', 'journal', 'result'):
        value = json.loads((tmp_path / 'new' / (name + '.json')).read_text())
        refs[name] = write(evidence, 'previous/' + name + '.json', value)
    request = deepcopy(request)
    request['previous_recoveries'] = [{'execution_id': ID, 'materials': refs}]
    facts = reconcile_original(request, original, evidence, api, snippets, trusted_rejection_exports=recovery.trusted_sources(request))
    preview = build_recovery_preview(request, facts)
    admission = deepcopy(data[2])
    admission.update(execution_id='fixture-recovery-2', request_digest=canonical_digest(request),
                     plan_digest=preview['preview_digest'].removeprefix('sha256:'))
    old_calls = len(api.new_calls)
    result = recovery.start(tmp_path / 'later', request, preview, admission, 'fixture-recovery-2', request['runtime']['image_digest'],
                            original, evidence, api, snippets)
    assert first['overall'] == result['overall'] == 'passed'
    assert result['facility_writes'] == 'none'
    assert result['full_original_resources'] == first['full_original_resources']
    assert result['previous_recoveries'] == request['previous_recoveries']
    assert all(row['status'] == 'already_absent' for row in result['resources'])
    assert len(api.new_calls) == old_calls
    request['full_original_resources']['volumes'] = request['full_original_resources']['volumes'][:1]
    with pytest.raises(Exception):
        recovery.plan(request, original, evidence, api, snippets)


@pytest.mark.parametrize('failure', ['timeout', 'invalid_status'])
def test_original_upid_cannot_be_observed_blocks_cleanup_after_approved_plan(tmp_path, failure):
    data = setup(tmp_path)
    api = data[-2]
    original_request = api.request
    def unavailable(method, path, **kwargs):
        if '/tasks/' in path and 'qmclone' in path:
            if failure == 'timeout':
                raise TimeoutError('protected-task-query')
            return {'status': 'unexpected'}
        return original_request(method, path, **kwargs)
    api.request = unavailable
    facts = reconcile_original(data[0], data[3], data[4], api, data[-1],
                               trusted_rejection_exports=recovery.trusted_sources(data[0]))
    assert facts['cleanup_eligible'] is False
    assert facts['task_activity_unresolved'] is True
    result = invoke(tmp_path, data)
    assert result['overall'] == 'unknown'
    assert result['facility_writes'] == 'none'
    assert api.new_calls == []
    assert data[-1].deletes == []


def test_retained_guest_pid_is_current_activity_not_missing_historical_correlation(tmp_path):
    from test_pve_acceptance_recovery_evidence import write
    data = list(setup(tmp_path))
    request, _, admission, original, evidence, api, snippets = data
    journal = json.loads((original / 'journal.json').read_text())
    journal['tasks'][-1]['pid'] = 42
    request['original_materials']['journal'] = write(original, 'journal.json', journal)
    facts = reconcile_original(request, original, evidence, api, snippets,
                               trusted_rejection_exports=recovery.trusted_sources(request))
    assert facts['cleanup_eligible'] is False
    assert facts['task_activity_unresolved'] is True
    preview = build_recovery_preview(request, facts)
    admission.update(request_digest=canonical_digest(request), plan_digest=preview['preview_digest'].removeprefix('sha256:'))
    data[:3] = [request, preview, admission]
    assert invoke(tmp_path, data)['overall'] == 'unknown'
    assert api.new_calls == []
    assert snippets.deletes == []


def test_unknown_previous_recovery_blocks_cleanup_despite_current_absence(tmp_path):
    from test_pve_acceptance_recovery_evidence import write
    data = setup(tmp_path)
    data[-2].lost = True
    first = invoke(tmp_path, data)
    assert first['overall'] == 'unknown'
    request, _, _, original, evidence, api, snippets = data
    refs = {name: write(evidence, 'previous/' + name + '.json', json.loads((tmp_path / 'new' / (name + '.json')).read_text()))
            for name in ('request', 'journal', 'result')}
    request = deepcopy(request)
    request['previous_recoveries'] = [{'execution_id': ID, 'materials': refs}]
    api.lost = False
    api.present = False
    api.volumes.clear()
    snippets.present = False
    preview = recovery.plan(request, original, evidence, api, snippets)
    assert preview['reconciliation']['cleanup_eligible'] is False
    assert preview['reconciliation']['previous_activity'] == 'unknown'
    assert preview['reconciliation']['disposition'] == 'blocked'
    assert len(api.new_calls) == 1


def test_result_collection_failure_keeps_unknown_and_observe_does_not_start(tmp_path, monkeypatch):
    data = setup(tmp_path)
    original_save = recovery.save
    def save(path, value):
        if path == tmp_path / 'new/result.json':
            raise OSError('fixture collection unavailable')
        return original_save(path, value)
    monkeypatch.setattr(recovery, 'save', save)
    result = invoke(tmp_path, data)
    assert result['overall'] == 'unknown'
    assert result['collection']['status'] == 'incomplete'
    assert result['facility_writes'] == 'issued'
    before = len(data[-2].new_calls)
    assert recovery.observe(tmp_path / 'new', ID)[1] is None
    assert len(data[-2].new_calls) == before


def test_snippet_disappears_before_helper_delete_reports_already_absent_without_new_write(tmp_path):
    data = setup(tmp_path)
    api, snippets = data[-2:]
    api.present = False
    api.volumes.clear()
    def delete(snippet):
        snippets.deletes.append(deepcopy(snippet))
        snippets.present = False
        return {'status': 'already_absent'}
    snippets.delete = delete
    result = invoke(tmp_path, data)
    assert result['overall'] == 'passed'
    assert result['facility_writes'] == 'none'
    row = next(r for r in result['resources'] if r['kind'] == 'snippet')
    assert row['status'] == 'already_absent'
    assert row['reason_code'] == 'current_absence_observed'
    assert api.new_calls == []


@pytest.mark.parametrize('timeout', [recovery.DeadlineExpired, recovery.LocalTimeout])
def test_snippet_cutoff_between_intent_and_dispatch_is_not_sent(tmp_path, monkeypatch, timeout):
    data = setup(tmp_path)
    api, snippets = data[-2:]
    api.present = False
    api.volumes.clear()
    remaining = recovery.Recovery.remaining
    def bounded(self):
        tasks = self.journal['tasks']
        if tasks and tasks[-1]['phase'] == 'snippet_delete' and tasks[-1]['status'] == 'intent':
            if timeout is recovery.DeadlineExpired:
                self.budget.outcome = {'phase': 'cleanup', 'status': 'exceeded'}
            raise timeout('cleanup')
        return remaining(self)
    monkeypatch.setattr(recovery.Recovery, 'remaining', bounded)
    result = invoke(tmp_path, data)
    assert result['overall'] == 'failed'
    assert result['facility_writes'] == 'none'
    assert snippets.deletes == []
    journal = json.loads((tmp_path / 'new/journal.json').read_text())
    assert journal['tasks'][-1]['status'] == 'not_sent'
    assert journal['mutation_active'] is False
    assert recovery.observe(tmp_path / 'new', ID)[1] == result


def test_snippet_helper_response_loss_remains_unknown(tmp_path):
    data = setup(tmp_path)
    api, snippets = data[-2:]
    api.present = False
    api.volumes.clear()
    def delete(snippet):
        snippets.deletes.append(deepcopy(snippet))
        raise TimeoutError('fixture response unavailable')
    snippets.delete = delete
    result = invoke(tmp_path, data)
    assert result['overall'] == 'unknown'
    assert result['facility_writes'] == 'unknown'
    journal = json.loads((tmp_path / 'new/journal.json').read_text())
    assert journal['tasks'][-1]['status'] == 'unknown'
    assert journal['mutation_active'] is True


@pytest.mark.parametrize('missing', ['VM.PowerMgmt', 'Datastore.AllocateSpace'])
def test_missing_cleanup_permission_rejects_before_new_facility_writes(tmp_path, missing):
    data = setup(tmp_path)
    api, snippets = data[-2:]
    original = api.request
    def request(method, path, **kwargs):
        response = original(method, path, **kwargs)
        if path.endswith('/access/permissions'):
            grant_path = kwargs['fields']['path']
            response[grant_path].pop(missing, None)
        return response
    api.request = request
    result = invoke(tmp_path, data)
    assert result['overall'] == 'failed'
    assert result['reason_code'] == 'permission_missing'
    diagnostic = result['reconciliation']['permission_diagnostic']
    assert diagnostic['reason_code'] == 'permission_missing'
    assert missing in diagnostic['missing_privileges']
    assert result['facility_writes'] == 'none'
    assert api.new_calls == []
    assert snippets.deletes == []

    from iaas.pve_template.admission import AdmissionError
    with pytest.raises(AdmissionError, match='^permission_missing$'):
        recovery.plan(data[0], data[3], data[4], api, snippets)
    assert api.new_calls == []


def test_preview_frozen_proof_drift_refuses_all_cleanup_writes(tmp_path):
    data = setup(tmp_path)
    request, preview, approved = data[:3]
    changed = deepcopy(preview['reconciliation'])
    changed['proof_bindings']['request_digest'] = 'sha256:' + '0' * 64
    preview = build_recovery_preview(request, changed)
    approved['plan_digest'] = preview['preview_digest'].removeprefix('sha256:')
    data = (request, preview, approved, *data[3:])
    result = invoke(tmp_path, data)
    assert result['overall'] != 'passed'
    assert data[-2].new_calls == []
    assert data[-1].deletes == []


@pytest.mark.parametrize('current_change', ['absent', 'marker', 'uuid', 'extra_volume', 'marker_after_reconcile'])
def test_pre_registration_reviewed_scope_rejects_drift_or_cleans_exact_absent_remnants(tmp_path, current_change):
    from test_pve_acceptance_recovery_evidence import candidate_fixture
    from test_pve_template_acceptance import API as CloneAPI
    original_root, evidence_root, request, original_journal, original_request = candidate_fixture(tmp_path)
    candidate = original_journal['clone_candidate']
    class OrphanAPI(CloneAPI):
        def request(self, method, path, fields=None, **kwargs):
            if path == '/api2/json/nodes':
                return [{'node': 'pve1'}]
            if path.endswith('/status/current') and current_change == 'marker_after_reconcile':
                self.clone['description'] = 'iaas-acceptance-clone:33333333-3333-4333-8333-333333333333'
            if method == 'DELETE' and '/content/' in path:
                from urllib.parse import unquote
                self.calls.append((method, path, fields, kwargs))
                self.volumes.remove(unquote(path.rsplit('/', 1)[1]))
                return self.task('volume_delete')
            return super().request(method, path, fields, **kwargs)
    api = OrphanAPI(original_request)
    api.clone = {**api.source, 'template': 0, 'description': original_journal['clone_marker'],
                 'smbios1': 'uuid=' + candidate['smbios_uuid'],
                 **{slot: volid + ',size=8G' for slot, volid in candidate['slots'].items()}}
    api.volumes = sorted(candidate['slots'].values())
    class Helpers:
        def inspect(self):
            return {'complete': True, 'local_node': 'pve1', 'nodes': ['pve1'],
                    'vmids': [9000, 9100] if api.clone else [9000], 'references': [],
                    'volume_references': [], 'snippet_references': []}
    helper = Helpers()
    facts = reconcile_original(request, original_root, evidence_root, api, helper)
    assert facts['cleanup_eligible'] is True
    preview = build_recovery_preview(request, facts)
    approved = {'schema_version': 2, 'execution_id': ID,
        'plan_digest': preview['preview_digest'].removeprefix('sha256:'), 'request_digest': canonical_digest(request),
        'runtime': request['runtime'], 'target': request['target'], 'deadlines': request['deadlines'], 'approved': True,
        'consumption': {'reserved': True, 'reservation_id': 'new-reservation'},
        'pending': {'record_id': 'new-pending', 'execution_id': CALLER},
        'serialization': {'held': True, 'context_id': 'new-context'}, 'recovery_of': ORIGINAL,
        'vmid_reservation': {'cluster_scope': request['cluster_scope'], 'vmids': [9100], 'reservation_id': 'new-reservation', 'context_id': 'new-context'}}
    if current_change == 'absent':
        api.clone = None
        api.volumes = api.volumes[:1]
    elif current_change == 'marker':
        api.clone['description'] = 'iaas-acceptance-clone:33333333-3333-4333-8333-333333333333'
    elif current_change == 'uuid':
        api.clone['smbios1'] = 'uuid=33333333-3333-4333-8333-333333333333'
    elif current_change == 'extra_volume':
        api.clone['scsi1'] = 'local-lvm:vm-9100-extra,size=8G'
    api.calls.clear()
    result = recovery.start(tmp_path / 'new', request, preview, approved, ID, request['runtime']['image_digest'],
                            original_root, evidence_root, api, helper)
    writes = [(method, path) for method, path, *_ in api.calls if method != 'GET']
    if current_change != 'absent':
        assert result['overall'] != 'passed' and writes == []
        return
    assert result['overall'] == 'passed'
    assert len(writes) == 1 and writes[0][0] == 'DELETE' and '/content/' in writes[0][1]
    assert next(r for r in result['resources'] if r['kind'] == 'vm')['status'] == 'already_absent'
