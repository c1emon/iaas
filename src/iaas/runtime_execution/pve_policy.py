"""Frozen ordinary VM placement and caller-owned cluster reservation bindings."""
from __future__ import annotations

from copy import deepcopy
from collections.abc import Sequence
from typing import Any, cast

from iaas.common.errors import require

VM_TYPE = 'proxmox_virtual_environment_vm'


def vm_policy(inputs: dict, cluster_scope: Any, changes: Sequence[dict] = ()) -> dict:
    require(isinstance(cluster_scope, str) and bool(cluster_scope.strip()),
            'ordinary PVE operation requires a stable caller cluster_scope')
    placements = sorted([{'node': vm['node'], 'vmid': vm['vmid'], 'pool': vm['pool']}
                         for vm in inputs['vms']], key=lambda vm: vm['vmid'])
    vmids = {vm['vmid'] for vm in placements}
    for item in changes:
        if item['type'] != VM_TYPE:
            continue
        change = item['change']
        for value in (change.get('before'), change.get('after')):
            if value:
                require(type(value.get('vm_id')) is int, 'native VMID must be concrete')
                vmids.add(value['vm_id'])
        after = change.get('after')
        if after:
            matches = [vm for vm in placements if vm['vmid'] == after.get('vm_id')]
            require(len(matches) == 1 and matches[0]['node'] == after.get('node_name')
                    and 'pool_id' in after and matches[0]['pool'] == after['pool_id']
                    and not change.get('after_unknown', {}).get('pool_id'),
                    'native VM placement or pool conflicts with selected inputs')
    return {'cluster_scope': cluster_scope, 'reserved_vm_id_ranges': deepcopy(inputs['cluster']['reserved_vm_id_ranges']),
            'placements': placements, 'vmids': sorted(vmids)}


def bind_policy(metadata: dict, frozen_inputs: dict, current_inputs: dict | None = None,
                cluster_scope: Any = None) -> None:
    policy = metadata.get('vm_policy')
    require(isinstance(policy, dict), 'saved VM policy is missing; prepare a new plan')
    policy = cast(dict, policy)
    require(policy == vm_policy(frozen_inputs, policy.get('cluster_scope'), metadata['changes']),
            'saved pool, VMID or reservation policy conflicts with companions')
    if current_inputs is not None:
        require(policy == vm_policy(current_inputs, cluster_scope, metadata['changes']),
                'current pool, VMID or reservation policy differs from reviewed plan')


def admit_reservation(admission: dict, policy: dict) -> None:
    from .pve_contracts import validate_vmid_reservation
    validate_vmid_reservation(admission, cluster_scope=policy['cluster_scope'], vmids=policy['vmids'])


def admit_permissions(changes: list[dict], api: Any) -> None:
    from iaas.pve_template.admission import Permissions

    permissions = Permissions(api)
    fields = {'cpu': 'VM.Config.CPU', 'memory': 'VM.Config.Memory',
              'network_device': 'VM.Config.Network', 'disk': 'VM.Config.Disk',
              'initialization': 'VM.Config.Cloudinit', 'hostpci': 'VM.Config.HWType',
              'started': 'VM.PowerMgmt', 'cdrom': 'VM.Config.CDROM'}
    for item in changes:
        if item['type'] != VM_TYPE:
            continue
        change = item['change']
        before, after = change.get('before') or {}, change.get('after') or {}
        value = after or before
        pool = value.get('pool_id')
        required = {'VM.Audit'}
        if 'create' in change['actions'] or 'delete' in change['actions']:
            required.add('VM.Allocate')
        if 'delete' in change['actions']:
            required.add('VM.PowerMgmt')
        for name in set(before) | set(after):
            if before.get(name) != after.get(name) and name not in {'id', 'vm_id', 'node_name', 'pool_id', 'clone'}:
                required.add(fields.get(name, 'VM.Config.Options'))
        if pool is not None:
            permissions.pool(pool)
        permissions.placement(value['vm_id'], pool, sorted(required), future='create' in change['actions'])
        for source in after.get('clone', []) if 'create' in change['actions'] else []:
            permissions.require(f"/vms/{source['vm_id']}", ['VM.Audit', 'VM.Clone'], operation='clone_source')
