from copy import deepcopy
import json
from types import SimpleNamespace

import pytest

from iaas_automation.common.errors import ValidationError
from iaas_automation.runtime_execution.plans import _templates, _admit_templates

TARGET = {'api_endpoint': 'https://pve.invalid:8006', 'insecure': False,
          'storage_id': 'snippets', 'ssh_host': 'ssh.invalid', 'ssh_user': 'ops'}
RECORD_TARGET = {'api_endpoint': TARGET['api_endpoint'], 'node': 'n1', 'tls_verify': True}
OBJECT = {'node': 'n1', 'vmid': 9001, 'smbios_uuid': 'original-uuid', 'disks': {'scsi0': 'local:base-9001-disk-0'}}
RECORD = {'kind': 'pve-template-record', 'schema_version': 2, 'record_id': 'build-1',
          'target': RECORD_TARGET, 'node': 'n1', 'vmid': 9001, 'smbios_uuid': 'original-uuid',
          'volumes': {'scsi0': 'local:base-9001-disk-0'},
          'configuration': {'cores': 2, 'memory': 2048, 'template': 1}, 'origin': 'publication',
          'execution_id': 'build-1', 'artifact_digest': 'sha256:' + 'b' * 64,
          'verification': {'template_config': 'passed', 'guest_acceptance': 'not_performed'}}


class API:
    def vm_config(self, *args):
        return {'smbios1': 'uuid=original-uuid', 'scsi0': 'local:base-9001-disk-0,size=8G',
                'cores': 2, 'memory': 2048, 'template': 1}


def selected(tmp_path, admission):
    paths = {}
    for name, value in [('template_records', {'records': [RECORD]}), ('template_admission', {'admissions': [admission]})]:
        path = tmp_path / (name + '.json')
        path.write_text(json.dumps(value))
        path.chmod(0o600)
        paths[name] = path
    return SimpleNamespace(files=paths)


def material():
    admission = {'schema_version': 2, 'execution_id': 'apply-1', 'plan_digest': 'a' * 64,
                 'record_id': 'build-1', 'target': TARGET, 'purpose': 'execution', 'status': 'available',
                 'template_record': RECORD}
    metadata = {'target': TARGET, 'plan_digest': 'a' * 64, 'root_id': 'root', 'template_records': [RECORD],
                'template_use': {'purpose': 'execution', 'vmids': [501]}}
    return admission, metadata


def test_current_template_record_and_admission_bind_native_identity(tmp_path):
    admission, metadata = material()
    config = selected(tmp_path, admission)
    assert _templates(config, [{'node': 'n1', 'vmid': 9001}], TARGET, API()) == [RECORD]
    _admit_templates(metadata, config, 'apply-1', API())


@pytest.mark.parametrize('change', ['revoked', 'execution', 'object', 'missing'])
def test_current_template_admission_is_required(tmp_path, change):
    admission, metadata = (deepcopy(item) for item in material())
    if change == 'revoked':
        admission['status'] = 'revoked'
    if change == 'execution':
        admission['execution_id'] = 'another'
    if change == 'object':
        admission['template_record']['vmid'] = 9002
    if change == 'missing':
        admission['record_id'] = 'missing'
    with pytest.raises(ValidationError):
        _admit_templates(metadata, selected(tmp_path, admission), 'apply-1', API())


def test_same_vmid_rebuilt_is_rejected(tmp_path):
    admission, metadata = material()

    class Rebuilt(API):
        def vm_config(self, *args):
            return {**super().vm_config(*args), 'smbios1': 'uuid=replaced'}

    with pytest.raises(ValidationError, match='replaced|identity'):
        _admit_templates(metadata, selected(tmp_path, admission), 'apply-1', Rebuilt())


def test_pending_template_requires_plan_bound_temporary_scope(tmp_path):
    admission, metadata = deepcopy(material())
    admission.update(status='pending_validation', purpose='verification', approved=True, scope='root', vmids=[501])
    config = selected(tmp_path, admission)
    with pytest.raises(ValidationError, match='bounded'):
        _admit_templates(metadata, config, 'apply-1', API())
    metadata['template_use']['purpose'] = 'verification'
    _admit_templates(metadata, config, 'apply-1', API())


def test_update_delete_without_clone_does_not_check_publication():
    _, metadata = material()
    metadata = {**metadata, 'template_records': []}
    _admit_templates(metadata, SimpleNamespace(files={}), 'apply-1', object())


def test_state_ownership_allows_drift_but_markers_do_not_authorize_vmid():
    from iaas_automation.runtime_execution.plans import _check_declared_conflicts

    api = SimpleNamespace(
        effective_permissions=lambda path: {path: {'VM.Audit': 1}},
        cluster_vm_resources=lambda: [
            {'vmid': 501, 'node': 'n1', 'type': 'qemu',
             'name': 'changed-on-device', 'tags': 'managed-by-opentofu'}])
    state = {'resources': [{'type': 'proxmox_virtual_environment_vm', 'name': 'vm',
                            'instances': [{'attributes': {'node_name': 'n1', 'vm_id': 501}}]}]}
    _check_declared_conflicts([{'vmid': 501, 'name': 'desired'}], state, api)
    with pytest.raises(ValidationError, match='outside selected state'):
        _check_declared_conflicts([{'vmid': 501, 'name': 'changed-on-device'}], None, api)
