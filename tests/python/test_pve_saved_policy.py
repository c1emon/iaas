from copy import deepcopy

import pytest

from iaas.common.errors import ValidationError
from iaas.runtime_execution.pve_policy import vm_policy, bind_policy, admit_reservation


def inputs():
    return {'cluster': {'reserved_vm_id_ranges': {'acceptance': [800, 850]}},
            'vms': [{'node': 'node-a', 'vmid': 700, 'pool': 'operations'}]}


def change(action='create', pool='operations'):
    return {'type': 'proxmox_virtual_environment_vm', 'change': {'actions': [action],
            'after': {'node_name': 'node-a', 'vm_id': 700, 'pool_id': pool}}}


@pytest.mark.parametrize('field', ['pool', 'vmid', 'range', 'scope'])
def test_reviewed_policy_changes_rejected(field):
    frozen = inputs()
    changes = [change()]
    metadata = {'changes': changes, 'vm_policy': vm_policy(frozen, 'cluster-one', changes)}
    current = deepcopy(frozen)
    scope = 'cluster-one'
    if field == 'range':
        current['cluster']['reserved_vm_id_ranges']['acceptance'] = [800, 900]
    elif field == 'scope':
        scope = 'another-cluster'
    else:
        current['vms'][0][field] = {'pool': 'another-pool', 'vmid': 701}[field]
    with pytest.raises(ValidationError):
        bind_policy(metadata, frozen, current, scope)


@pytest.mark.parametrize('pool', [None, 'another-pool'])
def test_native_plan_cannot_drop_or_replace_pool(pool):
    with pytest.raises(ValidationError, match='native VM placement or pool'):
        vm_policy(inputs(), 'cluster-one', [change(pool=pool)])


@pytest.mark.parametrize('field', ['cluster_scope', 'vmids', 'reservation_id', 'context_id'])
def test_reservation_must_match_scope_ids_and_serialization(field):
    policy = vm_policy(inputs(), 'cluster-one')
    reservation = {'cluster_scope': 'cluster-one', 'vmids': [700],
                   'reservation_id': 'reserve-1', 'context_id': 'lock-1'}
    admission = {'consumption': {'reservation_id': 'reserve-1'},
                 'serialization': {'context_id': 'lock-1'}, 'vmid_reservation': reservation}
    admit_reservation(admission, policy)
    reservation[field] = {'cluster_scope': 'cluster-two', 'vmids': [701],
                          'reservation_id': 'reserve-2', 'context_id': 'lock-2'}[field]
    with pytest.raises(ValidationError, match='vmid_reservation_conflict'):
        admit_reservation(admission, policy)


def test_replacement_and_delete_include_original_vmid():
    replacement = change()
    replacement['change']['before'] = {'node_name': 'node-a', 'vm_id': 699, 'pool_id': 'operations'}
    assert vm_policy(inputs(), 'cluster-one', [replacement])['vmids'] == [699, 700]


def test_pool_permission_recheck_is_readonly_and_refuses_missing_grants():
    from iaas.pve_template.admission import AdmissionError
    from iaas.runtime_execution.pve_policy import admit_permissions

    class Api:
        grants = {'VM.Audit': 1, 'VM.Allocate': 1}
        calls = []

        def effective_permissions(self, path):
            self.calls.append(('permissions', path))
            return {path: self.grants}

        def pool_detail(self, pool):
            self.calls.append(('pool', pool))
            return {'members': []}

    api = Api()
    admit_permissions([change()], api)
    assert ('pool', 'operations') in api.calls
    api.grants = {'VM.Audit': 1}
    with pytest.raises(AdmissionError, match='permission_missing'):
        admit_permissions([change()], api)


def test_allocate_only_creation_refuses_missing_lifecycle_permissions():
    from iaas.pve_template.admission import AdmissionError
    from iaas.runtime_execution.pve_policy import admit_permissions
    class Api:
        def pool_detail(self, pool):
            return {'members': []}
        def effective_permissions(self, path):
            if path.startswith('/pool/'):
                return {path: {'VM.Allocate': 0}}
            return {path: {}}
    with pytest.raises(AdmissionError, match='permission_missing'):
        admit_permissions([change()], Api())


@pytest.mark.parametrize('pool_only', [False, True])
def test_create_prechecks_configuration_permissions_and_rejects_unproven_future_acl(pool_only):
    from iaas.pve_template.admission import AdmissionError
    from iaas.runtime_execution.pve_policy import admit_permissions
    item = change()
    item['change']['after']['cpu'] = {'cores': 2}
    class Api:
        def pool_detail(self, pool):
            return {'members': []}
        def effective_permissions(self, path):
            grants = {'VM.Audit': 0, 'VM.Allocate': 0}
            if pool_only:
                grants['VM.Config.CPU'] = 0
                if path.startswith('/vms/'):
                    grants = {}
            return {path: grants}
    reason = 'permission_evidence_insufficient' if pool_only else 'permission_missing'
    with pytest.raises(AdmissionError, match=reason):
        admit_permissions([item], Api())


def test_state_owned_update_is_allowed_but_replaced_identity_rejected():
    from iaas.runtime_execution.plans import _check_resource_conflicts

    item = change(action='update')
    item['address'] = 'proxmox_virtual_environment_vm.test'
    item['change']['before'] = {'node_name': 'node-a', 'vm_id': 700, 'pool_id': 'old-pool'}
    state = {'resources': [{'type': 'proxmox_virtual_environment_vm', 'name': 'test', 'instances': [
        {'attributes': {'node_name': 'node-a', 'vm_id': 700, 'smbios': [{'uuid': 'original-uuid'}]}}]}]}

    class Api:
        uuid = 'original-uuid'

        def vm_config(self, node, vmid):
            return {'smbios1': 'uuid=' + self.uuid, 'scsi0': 'local:vm-700-disk-0,size=8G'}

    api = Api()
    _check_resource_conflicts([item], state, api)
    api.uuid = 'replacement-uuid'
    with pytest.raises(ValidationError, match='managed VM identity changed'):
        _check_resource_conflicts([item], state, api)


@pytest.mark.parametrize('denied', [None, 'old-pool', 'operations'])
def test_existing_pool_move_checks_both_membership_permissions(denied):
    from iaas.pve_template.admission import AdmissionError
    from iaas.runtime_execution.pve_policy import admit_permissions

    item = change(action='update')
    item['change']['before'] = {'node_name': 'node-a', 'vm_id': 700, 'pool_id': 'old-pool'}

    class Api:
        def pool_detail(self, pool):
            return {'members': []}

        def effective_permissions(self, path):
            grants = {'VM.Audit': 1, 'Permissions.Modify': 0}
            if path != f'/pool/{denied}':
                grants['Pool.Allocate'] = 0
            return {path: grants}

    if denied is None:
        admit_permissions([item], Api())
    else:
        with pytest.raises(AdmissionError, match='permission_missing'):
            admit_permissions([item], Api())


def test_provider_unsupported_existing_pool_removal_refused():
    from iaas.runtime_execution.pve_policy import admit_permissions
    item = change(action='update', pool=None)
    item['change']['before'] = {'node_name': 'node-a', 'vm_id': 700, 'pool_id': 'old-pool'}
    with pytest.raises(ValidationError, match='provider cannot remove'):
        admit_permissions([item], object())
