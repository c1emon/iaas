from copy import deepcopy
import json
from pathlib import Path

import pytest

from iaas.pve_template.admission import (ACCEPTANCE_PRIVILEGES, AdmissionError, Permissions,
    admit_acceptance, disk_capacity, require_free_vmid, require_helper_capabilities)

ROOT = Path(__file__).resolve().parents[2]


class API:
    def __init__(self, request):
        self.request_data = request
        self.calls = []
        self.permissions = {}
        self.capacity = 100 * 1024 ** 3

    def request(self, method, path, *, fields=None):
        self.calls.append((method, path))
        assert method == 'GET'
        if path.endswith('/access/permissions'):
            acl = fields['path']
            return {acl: self.permissions.get(acl, {name: 0 for name in (*ACCEPTANCE_PRIVILEGES,
                'VM.Clone', 'Datastore.Audit', 'Datastore.AllocateSpace', 'Sys.Audit', 'SDN.Use')})}
        if '/pools/' in path:
            return {'members': []}
        if path.endswith('/cluster/status'):
            return [{'name': 'pve1', 'type': 'node', 'online': 1}]
        if '/storage/' in path and path.endswith('/status'):
            return {'enabled': 1, 'active': 1, 'content': 'images,snippets', 'type': 'dir', 'avail': self.capacity}
        if path.endswith('/status'):
            return {'cpuinfo': {'cpus': 8}, 'memory': {'total': 16 * 1024 ** 3}}
        if path.endswith('/config'):
            return deepcopy(self.request_data['template_record']['configuration'])
        if path.endswith('/network'):
            return [{'iface': 'vmbr0', 'type': 'bridge', 'active': 1, 'bridge_vlan_aware': 1}]
        raise AssertionError(path)


class Helpers:
    def capabilities(self, name):
        keys = ('acceptance', 'create_only', 'verify', 'deadline') if name == 'upload' else ('inspect', 'exact_delete', 'reference', 'digest', 'deadline')
        return {'schema_version': 'helper-capabilities/v1', 'helper': name,
                'protocol_version': 2, 'capabilities': dict.fromkeys(keys, True)}

    def inspect(self):
        return {'complete': True, 'local_node': 'pve1', 'nodes': ['pve1'], 'vmids': [9000]}


@pytest.fixture
def request_data():
    value = json.loads((ROOT / 'docs/examples/pve-acceptance/acceptance-request.json').read_text())
    value['temporary_vm']['pool'] = 'acceptance'
    return value


def test_complete_readonly_admission_and_auxiliary_capacity(request_data):
    api = API(request_data)
    result = admit_acceptance(api, request_data, helpers=Helpers())
    assert result['readiness']['status'] == 'ready'
    assert result['capacity']['total_required_bytes'] == 8 * 1024 ** 3 + 4 * 1024 ** 2
    assert [row['slot'] for row in result['capacity']['disks']] == ['scsi0', 'ide2']
    assert all(method == 'GET' for method, _ in api.calls)


@pytest.mark.parametrize(('grants', 'reason'), [({}, 'permission_missing'),
    ({'VM.Clone': -1}, 'permission_value_invalid'), (None, 'permission_evidence_insufficient')])
def test_permission_classifications(request_data, grants, reason):
    api = API(request_data)
    api.permissions['/vms/9000'] = grants
    with pytest.raises(AdmissionError) as caught:
        Permissions(api).require('/vms/9000', ['VM.Clone'])
    assert caught.value.reason_code == reason


def test_query_failure_never_copies_sensitive_exception():
    class Failed:
        def request(self, *args, **kwargs):
            raise RuntimeError('TOKEN private-response')
    with pytest.raises(AdmissionError) as caught:
        Permissions(Failed()).grants('/vms/9100')
    assert caught.value.reason_code == 'permission_query_failed'
    assert 'TOKEN' not in str(caught.value.diagnostic)


def test_pool_allocation_is_or_and_future_inheritance_has_noaccess_boundary(request_data):
    api = API(request_data)
    api.permissions['/vms/9100'] = {'VM.Audit': 0}
    result = Permissions(api).placement(9100, 'acceptance', ACCEPTANCE_PRIVILEGES)
    assert result['permission_path'] == '/pool/acceptance'
    api.permissions['/vms/9100'] = {}
    with pytest.raises(AdmissionError, match='permission_evidence_insufficient'):
        Permissions(api).placement(9100, 'acceptance', ACCEPTANCE_PRIVILEGES)
    api.permissions['/vms/9100'] = {name: 0 for name in ACCEPTANCE_PRIVILEGES if name != 'VM.Allocate'}
    # Allocation may be granted by the pool while all dependent lifecycle grants
    # are direct. No redundant direct allocation grant is required.
    assert Permissions(api).placement(9100, 'acceptance', ACCEPTANCE_PRIVILEGES)


def test_existing_vm_update_does_not_require_allocate(request_data):
    api = API(request_data)
    api.permissions['/vms/9100'] = {'VM.Config.Network': 0}
    api.permissions['/pool/acceptance'] = {}
    assert Permissions(api).placement(9100, 'acceptance', ('VM.Config.Network',), future=False)


def test_guest_unrestricted_satisfies_informational_and_exec_permissions(request_data):
    api = API(request_data)
    assert 'VM.GuestAgent.Audit' not in ACCEPTANCE_PRIVILEGES
    admit_acceptance(api, request_data, helpers=Helpers())
    api.permissions['/vms/9100'] = {name: 0 for name in ACCEPTANCE_PRIVILEGES if name != 'VM.GuestAgent.Unrestricted'}
    api.permissions['/pool/acceptance'] = {'VM.Allocate': 0, 'VM.GuestAgent.Audit': 0}
    with pytest.raises(AdmissionError, match='permission_missing'):
        admit_acceptance(api, request_data, helpers=Helpers())


def test_complete_helper_occupancy_rejects_filtered_or_foreign_cluster():
    snapshot = Helpers().inspect()
    require_free_vmid(9100, snapshot, node='pve1', cluster_nodes=['pve1'])
    for changed in ({'complete': False}, {'nodes': ['other']}, {'local_node': 'other'}, {'vmids': [9100]}):
        with pytest.raises(AdmissionError) as caught:
            require_free_vmid(9100, snapshot | changed, node='pve1', cluster_nodes=['pve1'])
        assert caught.value.reason_code in ('permission_evidence_insufficient', 'vmid_occupied')


def test_helper_missing_capability_refused():
    declaration = Helpers().capabilities('delete')
    declaration['capabilities']['reference'] = False
    with pytest.raises(AdmissionError, match='helper_capability_missing'):
        require_helper_capabilities(declaration, 'delete')


def test_disk_limit_diagnostic_is_total_and_unknown_disk_refused(request_data):
    config = request_data['template_record']['configuration']
    config['scsi0'] = 'local-lvm:vm-9000-disk-0,size=40G'
    with pytest.raises(AdmissionError) as caught:
        disk_capacity(API(request_data), config, request_data['template_record'], 40 * 1024 ** 3)
    assert caught.value.reason_code == 'disk_limit_exceeded'
    assert caught.value.diagnostic['capacity']['total_required_bytes'] == 42_953_867_264
    config['efidisk0'] = 'local-lvm:vm-9000-disk-1'
    with pytest.raises(AdmissionError, match='disk_size_unknown'):
        disk_capacity(API(request_data), config, request_data['template_record'], 100 * 1024 ** 3)


def test_storage_capacity_refused_before_helpers(request_data):
    api = API(request_data)
    api.capacity = 1
    with pytest.raises(AdmissionError, match='storage_capacity_insufficient'):
        admit_acceptance(api, request_data, helpers=None)


@pytest.mark.parametrize('change', ['source', 'node', 'network', 'pool'])
def test_required_readiness_failures_are_readonly(request_data, change):
    api = API(request_data)
    original = api.request
    def changed(method, path, *, fields=None):
        value = original(method, path, fields=fields)
        if change == 'source' and path.endswith('/config'):
            value['name'] = 'changed'
        if change == 'node' and path.endswith('/cluster/status'):
            value[0]['online'] = 0
        if change == 'network' and path.endswith('/network'):
            value = []
        if change == 'pool' and '/pools/' in path:
            value = None
        return value
    api.request = changed
    with pytest.raises(AdmissionError):
        admit_acceptance(api, request_data, helpers=Helpers())
    assert all(method == 'GET' for method, _ in api.calls)
