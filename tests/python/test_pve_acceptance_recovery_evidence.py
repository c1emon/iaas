"""Sanitized run-120-1 structure; fake API evidence is not live recovery."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest

from iaas.pve_acceptance_contracts import canonical_digest
from iaas.pve_template.recovery_contracts import build_recovery_preview, validate_recovery_preview, validate_recovery_request
from iaas.pve_template.recovery_evidence import RecoveryEvidenceError, load_original, reconcile_original

ORIGINAL = '01591395-b75d-4108-a19d-7e5ccdb99acc-accept'
CALLER = '01591395-b75d-4108-a19d-7e5ccdb99acc'
VM_UUID = '22222222-2222-4222-8222-222222222222'
VOLUMES = ['local-lvm:vm-798-disk-0', 'local-lvm:vm-798-cloudinit']
SNIPPET = 'local:snippets/iaas-accept-fixture-798-user-data.yml'
PRINCIPAL = 'fixture@pve!automation'


def write(root, name, value):
    path = root / name
    path.parent.mkdir(exist_ok=True, parents=True)
    raw = (json.dumps(value, sort_keys=True) + '\n').encode()
    path.write_bytes(raw)
    return {'path': name, 'sha256': hashlib.sha256(raw).hexdigest()}


def fixture(tmp_path):
    original_root, evidence_root = tmp_path / 'original', tmp_path / 'evidence'
    # Explicit retained rc.19 bytes; no new validator/normalization is involved.
    old = json.loads((Path(__file__).resolve().parents[2] / 'docs/examples/recovery/original/request.json').read_text())
    old['schema_version'] = 2
    for key in ('cluster_scope', 'runtime', 'vmid_policy'):
        old.pop(key, None)
    old['temporary_vm'].pop('pool', None)
    old['template_record']['schema_version'] = 2
    old['template_record'].pop('cluster_scope', None)
    old['template_record'].pop('pool', None)
    old['target']['node'] = 'cohe'
    old['template_record'].update(target=deepcopy(old['target']), node='cohe', vmid=9004)
    old['temporary_vm'].update(node='cohe', vmid=798)
    old['deadlines'] = {'work_deadline_at': '2026-09-30T00:00:00Z', 'cleanup_deadline_at': '2026-09-30T00:10:00Z'}
    digest = canonical_digest(old)
    old_runtime = {'image_digest': 'runtime@sha256:' + 'a' * 64}
    snippet = {'node': 'cohe', 'vmid': 798, 'storage': 'local', 'file_name': SNIPPET.split('/', 1)[1],
               'file_id': SNIPPET, 'sha256': 'd' * 64, 'uploaded': True}
    tasks = [{'phase': 'clone', 'node': 'cohe', 'status': 'succeeded',
              'upid': 'UPID:cohe:00000001:00000001:00000001:qmclone:798:root@pam:'},
             {'phase': 'configure', 'status': 'succeeded'},
             {'phase': 'start', 'node': 'cohe', 'status': 'succeeded',
              'upid': 'UPID:cohe:00000001:00000001:00000002:qmstart:798:root@pam:'},
             {'phase': 'guest_exec', 'status': 'unknown'}]
    admission = {'schema_version': 1, 'execution_id': ORIGINAL, 'plan_digest': digest.removeprefix('sha256:'),
                 'target': old['target'], 'deadlines': old['deadlines'], 'approved': True,
                 'consumption': {'reserved': True, 'reservation_id': f'run-120-1:{CALLER}'},
                 'pending': {'record_id': f'astra-pve-template:{CALLER}'}, 'serialization': {'held': True, 'context_id': 'original-lock'}}
    journal = {'kind': 'pve-one-shot-journal', 'schema_version': 1, 'operation': 'accept',
               'execution_id': ORIGINAL, 'request_digest': digest, 'target': old['target'], 'deadlines': old['deadlines'],
               'runtime': old_runtime, 'admission': admission, 'mutation_active': True,
               'facility_writes': 'unknown', 'status': 'finished', 'tasks': tasks,
               'temporary_vm': {'node': 'cohe', 'vmid': 798, 'smbios_uuid': VM_UUID, 'volumes': VOLUMES},
               'snippets': [snippet]}
    dispatch = {'task_index': 3, 'authenticated_principal': PRINCIPAL, 'method': 'POST',
                'path': '/api2/json/nodes/cohe/qemu/798/agent/exec', 'node': 'cohe', 'vmid': 798,
                'dispatch_sequence': 4, 'dispatched_at': '2026-09-30T00:01:00Z'}
    caller = {'plan_id': 'run-120-1', 'execution_id': CALLER, 'native_execution_id': ORIGINAL,
              'pending_record_id': f'astra-pve-template:{CALLER}', 'reservation_id': f'run-120-1:{CALLER}',
              'request_digest': digest, 'runtime': old_runtime, 'dispatches': [dispatch]}
    log = {'source_id': 'pve-access-export', 'provenance': 'administrator_export', 'original_execution_id': ORIGINAL,
           'authenticated_principal': PRINCIPAL,
           'records': [{**dispatch, 'http_status': 403, 'rejected_before_execution': True}]}
    req_ref, journal_ref = write(original_root, 'request.json', old), write(original_root, 'journal.json', journal)
    caller_ref, log_ref = write(evidence_root, 'caller.json', caller), write(evidence_root, 'rejection.json', log)
    request = {'kind': 'pve-acceptance-recovery-request', 'schema_version': 1,
               'target': old['target'], 'cluster_scope': 'fixture-cluster',
               'runtime': {'image_digest': 'runtime@sha256:' + 'b' * 64},
               'deadlines': {'work_deadline_at': '2099-01-01T00:00:00Z', 'cleanup_deadline_at': '2099-01-01T00:10:00Z'},
               'timeouts': {'work_seconds': 600, 'cleanup_seconds': 180},
               'authorization': {'cleanup_original_resources': True}, 'original_execution_id': ORIGINAL,
               'caller_association': {'plan_id': 'run-120-1', 'execution_id': CALLER,
                                      'pending_record_id': f'astra-pve-template:{CALLER}', 'reservation_id': f'run-120-1:{CALLER}', 'material': caller_ref},
               'original_materials': {'request': req_ref, 'journal': journal_ref},
               'rejection_evidence': [{'material': log_ref, 'source_id': 'pve-access-export',
                                       'provenance': 'administrator_export', 'authenticated_principal': PRINCIPAL,
                                       'source_description': 'Sanitized fixture of an explicitly approved administrator export',
                                       'authorize_trusted_source': True}],
               'full_original_resources': {'vm': {'node': 'cohe', 'vmid': 798, 'smbios_uuid': VM_UUID, 'created_by': ORIGINAL},
                                           'volumes': VOLUMES,
                                           'snippets': [{'node': 'cohe', 'file_id': SNIPPET, 'sha256': 'd' * 64, 'created_by': ORIGINAL}]},
               'previous_recoveries': []}
    trusted = {'pve-access-export': {'sha256': log_ref['sha256'], 'provenance': 'administrator_export'}}
    return request, original_root, evidence_root, trusted


class API:
    active = False
    conflict = False
    def __init__(self):
        self.calls = []
    def request(self, method, path, *, fields=None):
        assert method == 'GET', 'readonly reconciliation must never dispatch a mutation'
        self.calls.append(path)
        if path.endswith('/access/permissions'):
            return {fields['path']: {name: 0 for name in ('VM.Audit', 'VM.Allocate', 'VM.PowerMgmt', 'Datastore.Audit', 'Datastore.AllocateSpace')}}
        if '/tasks/' in path and 'qmclone' in path:
            return {'status': 'running' if self.active else 'stopped', 'exitstatus': 'OK'}
        if '/tasks/' in path:
            return {'status': 'stopped', 'exitstatus': 'OK'}
        if path.endswith('/nodes'):
            return [{'node': 'cohe'}]
        if path.endswith('/cluster/resources'):
            return [{'vmid': 798, 'node': 'cohe', 'type': 'qemu', 'pool': 'existing-old-pool'},
                    {'vmid': 9004, 'node': 'cohe', 'type': 'qemu'}]
        if path.endswith('/qemu/798/config'):
            return {'smbios1': 'uuid=' + VM_UUID, 'scsi0': VOLUMES[0] + ',size=40G',
                    'ide2': VOLUMES[1] + ',media=cdrom,size=4M'}
        if path.endswith('/qemu/9004/config'):
            return {'scsi0': VOLUMES[0] if self.conflict else 'local-lvm:base-9004-disk-0'}
        if path.endswith('/content'):
            return [{'volid': v, 'vmid': 798} for v in VOLUMES]
        raise AssertionError(path)


class Snippets:
    def inspect(self):
        return {'complete': True, 'local_node': 'cohe', 'nodes': ['cohe'], 'vmids': [798, 9004], 'references': []}
    def inspect_file(self, snippet):
        return {'existence': 'present', 'sha256': snippet['sha256']}


def test_run120_reconciliation_preserves_original_bytes_and_does_not_apply_new_interval(tmp_path):
    request, original, evidence, trusted = fixture(tmp_path)
    before = {p: p.read_bytes() for p in original.iterdir()}
    api = API()
    result = reconcile_original(request, original, evidence, api, Snippets(), trusted_rejection_exports=trusted)
    assert result['cleanup_eligible'] is True
    assert result['original_activity'] == 'inactive'
    assert result['original_facility_writes'] == 'issued'
    assert result['requests'][-1]['reason_code'] == 'request_rejected'
    assert result['facility_writes'] == 'none'
    assert result['resources']['vm']['observed_pool'] == 'existing-old-pool'
    assert result['original_deadlines']['work_deadline_at'] == '2026-09-30T00:00:00Z'
    assert all(p.read_bytes() == content for p, content in before.items())
    preview = build_recovery_preview(request, result)
    assert validate_recovery_preview(preview) == preview
    assert 'pool' not in preview['fixed_input']['full_original_resources']['vm']
    assert preview['fixed_input']['caller_association'] == request['caller_association']


@pytest.mark.parametrize('field', ['pending_record_id', 'reservation_id'])
def test_namespaced_caller_references_must_match_original_verbatim(tmp_path, field):
    request, original, evidence, _ = fixture(tmp_path)
    assert validate_recovery_request(request) == request
    load_original(request, original, evidence)
    request['caller_association'][field] = request['caller_association'][field].replace(':', '-')
    with pytest.raises(RecoveryEvidenceError):
        load_original(request, original, evidence)


@pytest.mark.parametrize('fault', ['request_digest', 'caller', 'missing', 'resource_list', 'symlink'])
def test_core_binding_conflicts_refuse_without_api_calls(tmp_path, fault):
    request, original, evidence, trusted = fixture(tmp_path)
    if fault == 'request_digest':
        request['original_materials']['request']['sha256'] = 'f' * 64
    elif fault == 'caller':
        request['caller_association']['reservation_id'] = 'another'
    elif fault == 'missing':
        (original / 'journal.json').unlink()
    elif fault == 'resource_list':
        request['full_original_resources']['volumes'] = VOLUMES[:1]
    else:
        (original / 'request.json').unlink()
        (original / 'request.json').symlink_to(evidence / 'caller.json')
    api = API()
    with pytest.raises(Exception):
        reconcile_original(request, original, evidence, api, Snippets(), trusted_rejection_exports=trusted)
    assert api.calls == []


@pytest.mark.parametrize('fault', ['untrusted', 'ambiguous', 'principal', 'path', 'another_active', 'volume_reference'])
def test_unproven_rejection_or_other_activity_remains_unknown(tmp_path, fault):
    request, original, evidence, trusted = fixture(tmp_path)
    api = API()
    if fault == 'untrusted':
        trusted = {}
    elif fault == 'another_active':
        api.active = True
    elif fault == 'volume_reference':
        api.conflict = True
    else:
        log = json.loads((evidence / 'rejection.json').read_text())
        if fault == 'ambiguous':
            log['records'].append(deepcopy(log['records'][0]))
        elif fault == 'principal':
            log['records'][0]['authenticated_principal'] = 'other@pve!token'
        else:
            log['records'][0]['path'] = '/api2/json/nodes/cohe/qemu/799/agent/exec'
        ref = write(evidence, 'rejection.json', log)
        request['rejection_evidence'][0]['material'] = ref
        trusted['pve-access-export']['sha256'] = ref['sha256']
    result = reconcile_original(request, original, evidence, api, Snippets(), trusted_rejection_exports=trusted)
    blocked = fault in {'another_active', 'volume_reference'}
    assert result['cleanup_eligible'] is not blocked
    assert result['status'] == ('unknown' if blocked else 'eligible')
    if not blocked:
        assert result['original_activity'] == 'unknown'
        assert result['disposition'] == 'administrator_decision'
    assert result['facility_writes'] == 'none'


def test_recovery_contract_rejects_deadline_order_and_empty_cleanup_authority(tmp_path):
    request, *_ = fixture(tmp_path)
    request['deadlines']['work_deadline_at'] = '2099-01-02T00:00:00Z'
    with pytest.raises(Exception):
        validate_recovery_request(request)
    request['deadlines']['work_deadline_at'] = '2099-01-01T00:00:00Z'
    request['authorization']['cleanup_original_resources'] = False
    with pytest.raises(Exception):
        validate_recovery_request(request)


def test_available_legacy_result_is_digest_bound_and_never_promoted(tmp_path):
    request, original, evidence, trusted = fixture(tmp_path)
    old = json.loads((original / 'request.json').read_text())
    journal = json.loads((original / 'journal.json').read_text())
    template = {key: old['template_record'][key] for key in ('record_id', 'execution_id', 'artifact_digest', 'node', 'vmid', 'smbios_uuid')}
    result = {'kind': 'pve-template-acceptance-result', 'schema_version': 2, 'execution_id': ORIGINAL,
              'request_digest': journal['request_digest'], 'runtime': journal['runtime'], 'deadlines': old['deadlines'],
              'facility_writes': 'unknown', 'overall': 'unknown', 'template': template,
              'temporary_resources': [{'kind': kind, 'node': 'cohe', 'identity': identity,
                                       'created_by': ORIGINAL, 'ownership': 'owned'} for kind, identity in
                                      [('vm', '798'), *[('volume', v) for v in VOLUMES], ('snippet', SNIPPET)]]}
    request['original_materials']['result'] = write(original, 'result.json', result)
    journal['result_digest'] = canonical_digest(result)
    request['original_materials']['journal'] = write(original, 'journal.json', journal)
    before = (original / 'result.json').read_bytes()
    observed = reconcile_original(request, original, evidence, API(), Snippets(), trusted_rejection_exports=trusted)
    assert observed['original_acceptance'] == 'unknown'
    assert observed['cleanup_eligible'] is True
    assert (original / 'result.json').read_bytes() == before
    # A partial unknown result is informational; the journal owns the full list.
    result['temporary_resources'] = [dict(result['temporary_resources'][0], ownership='unknown')]
    request['original_materials']['result'] = write(original, 'result.json', result)
    journal['result_digest'] = canonical_digest(result)
    request['original_materials']['journal'] = write(original, 'journal.json', journal)
    assert load_original(request, original, evidence)['result'] == result
    result['overall'] = 'passed'
    request['original_materials']['result'] = write(original, 'result.json', result)
    with pytest.raises(RecoveryEvidenceError, match='original_result_binding_conflict'):
        load_original(request, original, evidence)


def test_recovery_preview_detects_pool_or_deadline_tamper(tmp_path):
    request, original, evidence, trusted = fixture(tmp_path)
    observed = reconcile_original(request, original, evidence, API(), Snippets(), trusted_rejection_exports=trusted)
    preview = build_recovery_preview(request, observed)
    preview['fixed_input']['full_original_resources']['vm']['pool'] = 'invented'
    with pytest.raises(Exception):
        validate_recovery_preview(preview)
    request['full_original_resources']['vm']['pool'] = 'invented'
    with pytest.raises(RecoveryEvidenceError, match='historical_pool_binding_conflict'):
        load_original(request, original, evidence)


def test_without_helper_reference_rows_filtered_api_is_not_a_complete_fallback(tmp_path):
    request, original, evidence, trusted = fixture(tmp_path)
    class Filtered(API):
        def request(self, method, path, **kwargs):
            response = super().request(method, path, **kwargs)
            if path.endswith('/cluster/resources'):
                return [row for row in response if row['vmid'] == 798]
            return response
    with pytest.raises(RecoveryEvidenceError, match='recovery_vm_inventory_incomplete'):
        reconcile_original(request, original, evidence, Filtered(), Snippets(), trusted_rejection_exports=trusted)
