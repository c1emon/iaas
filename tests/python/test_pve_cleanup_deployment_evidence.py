"""Cleanup must consume existing producer output, not a parallel invented format."""
import copy
import hashlib
import json
from pathlib import Path

import pytest

from iaas.pve_acceptance_contracts import validate_snippet_cleanup_request
from iaas.pve_inventory.cloud_init_helpers.artifacts import build_manifest
from iaas.pve_inventory.cloud_init_helpers.model import CloudInitSnippet
from iaas.pve_snippet_cleanup.evidence import validate_original
from iaas.runtime_execution.pve_results import expectations, machine_review
from iaas.runtime_execution.pve_state import StateObservation
from iaas.runtime_execution.state import S3Backend

FIXTURE = Path(__file__).resolve().parents[2] / 'docs/examples/pve-acceptance/cleanup-deployment-request.json'


def producer_materials(tmp_path):
    request = json.loads(FIXTURE.read_text())
    vm = request['original_vm']
    target = {**request['target'], 'root_id': 'root1', 'storage_id': 'local', 'ssh_host': 'pve.example.invalid', 'ssh_user': 'iaas'}
    backend = S3Backend({'bucket': 'state', 'key': 'vm.tfstate', 'region': 'local',
                         'endpoint': 'https://state.example.invalid', 'use_lockfile': True,
                         'use_path_style': True}, 'default')
    state = StateObservation('present', 'state', 'vm.tfstate', 'default', 'https://state.example.invalid',
                             lineage='lineage-001', serial=2, empty=True)
    attrs = {'vm_id': vm['vmid'], 'node_name': vm['node'], 'smbios': [{'uuid': vm['smbios_uuid']}]}
    change = {'address': 'proxmox_virtual_environment_vm.example', 'mode': 'managed',
              'type': 'proxmox_virtual_environment_vm', 'name': 'example',
              'change': {'actions': ['delete'], 'before': attrs, 'after': None}}
    _, changes, _ = machine_review({'resource_changes': [change]})
    digest = request['delete_plan']['plan_digest'].removeprefix('sha256:')
    metadata = {'schema_version': 2, 'plan_digest': digest, 'target': target, 'changes': changes,
                'backend': backend.identity(), 'root_id': 'root1', 'workspace': 'default'}
    context = {'execution_id': 'delete-001', 'plan_sha256': digest, 'target': target,
               'execution_admission': {'schema_version': 1, 'execution_id': 'delete-001', 'plan_digest': digest,
                                       'target': target, 'approved': True,
                                       'consumption': {'reserved': True, 'reservation_id': 'reserve-001'},
                                       'pending': {'record_id': 'pending-001'},
                                       'serialization': {'held': True, 'context_id': 'lock-001'}}}
    deleted = {'schema_version': 1, 'execution_id': 'delete-001', 'plan_digest': digest, 'target': target,
               'native_execution': {'status': 'success'}, 'state_persistence': {'status': 'passed'},
               'verification': {'status': 'passed'}, 'collection': {'status': 'passed'},
               'effects': {'facility': 'known', 'state': 'known', 'collection': 'known'},
               'expectations': expectations(changes, {'resources': []}), 'backend': backend.identity(),
               'root_id': 'root1', 'state_after': state.to_dict()}
    snippet = request['snippets'][0]
    tfvars = tmp_path / 'inputs.tfvars.json'
    tfvars.write_text('{}')
    manifest = build_manifest([CloudInitSnippet(vm['vmid'], 'example', snippet['file_name'], snippet['file_id'],
                                                '#cloud-config\n', sha256=snippet['sha256'])], tfvars, 'local')
    manifest['plan_sha256'] = 'a' * 64  # Added by save_plan after the native plan is written.
    create = copy.deepcopy(change)
    create['change'] = {'actions': ['create'], 'before': None, 'after': attrs}
    snapshot = {'resources': [{'mode': 'managed', 'type': change['type'], 'name': 'example',
                               'instances': [{'attributes': attrs}]}]}
    uploaded = {'execution_id': request['original_execution_id'], 'snippet_upload': 'completed',
                'target': target, 'plan_digest': manifest['plan_sha256'], 'expectations': expectations([create], snapshot)}
    documents = {'metadata': metadata, 'context': context, 'deleted': deleted, 'manifest': manifest, 'uploaded': uploaded}
    request['deletion_evidence']['state_persistence']['backend'] = backend.identity()
    return request, documents


def write_materials(tmp_path, request, documents):
    def ref(name):
        content = json.dumps(documents[name], sort_keys=True).encode()
        (tmp_path / (name + '.json')).write_bytes(content)
        return {'path': name + '.json', 'sha256': hashlib.sha256(content).hexdigest()}
    request['delete_plan'].update(metadata=ref('metadata'), admission=ref('context'))
    request['ownership_records'].update(manifest=ref('manifest'), upload=ref('uploaded'))
    deletion = request['deletion_evidence']
    deletion.update(result=ref('deleted'), vm_absence=ref('deleted'))
    deletion['state_persistence']['result'] = ref('deleted')
    return validate_snippet_cleanup_request(request)


def test_real_producer_shapes_bind_original_deployment(tmp_path):
    request, docs = producer_materials(tmp_path)
    validate_original(write_materials(tmp_path, request, docs), tmp_path)


@pytest.mark.parametrize('conflict', ['delete_target', 'admission_target', 'backend', 'state', 'manifest_digest',
                                     'missing_digest', 'upload_identity', 'delete_identity', 'scope', 'incomplete_collection'])
def test_original_producer_association_conflicts_refuse(tmp_path, conflict):
    request, docs = producer_materials(tmp_path)
    if conflict == 'delete_target':
        docs['deleted']['target'] = {**docs['deleted']['target'], 'node': 'other'}
    elif conflict == 'admission_target':
        docs['context']['target'] = {**docs['context']['target'], 'node': 'other'}
    elif conflict == 'backend':
        docs['metadata']['backend']['key'] = 'other.tfstate'
    elif conflict == 'state':
        docs['deleted']['state_after']['serial'] += 1
    elif conflict == 'manifest_digest':
        docs['manifest']['plan_sha256'] = 'f' * 64
    elif conflict == 'missing_digest':
        docs['manifest'].pop('plan_sha256')
        docs['uploaded'].pop('plan_digest')
    elif conflict == 'upload_identity':
        docs['uploaded']['expectations'][0]['native_identity'] = []
    elif conflict == 'delete_identity':
        docs['metadata']['changes'][0]['change']['before']['smbios'] = []
    elif conflict == 'scope':
        docs['manifest']['storage_id'] = 'other'
    else:
        docs['deleted']['collection']['status'] = 'unknown'
    with pytest.raises(ValueError):
        validate_original(write_materials(tmp_path, request, docs), tmp_path)
