"""Shared read-only PVE placement and full-clone acceptance admission.

Permission responses are effective grants for the authenticated principal, not
ACL rows or role names. Their 0/1 values are propagation flags, not booleans.
"""
from __future__ import annotations

from decimal import Decimal
import re
from typing import Any, cast
from urllib.parse import quote

from iaas.runtime_execution.execution import OperationFailed
from . import runtime as pve


class AdmissionError(OperationFailed):
    def __init__(self, reason_code: str, *, stage: str = 'admission', object: str | None = None,
                 operation: str | None = None, missing_privileges: list[str] | None = None,
                 http_status: int | None = None, capacity: dict | None = None):
        super().__init__(reason_code)
        self.reason_code = reason_code
        self.diagnostic: dict[str, Any] = {'reason_code': reason_code, 'stage': stage}
        for key, value in (('object', object), ('operation', operation),
                           ('missing_privileges', missing_privileges), ('http_status', http_status),
                           ('capacity', capacity)):
            if value is not None:
                self.diagnostic[key] = value


def _status(exc: Exception) -> int | None:
    value = getattr(exc, 'status_code', None)
    return value if type(value) is int and 100 <= value <= 599 else None


class Permissions:
    def __init__(self, client: Any):
        self.client = client

    def grants(self, path: str) -> dict:
        try:
            if hasattr(self.client, 'effective_permissions'):
                response = self.client.effective_permissions(path)
            else:
                response = self.client.request('GET', '/api2/json/access/permissions', fields={'path': path})
        except Exception as exc:
            raise AdmissionError('permission_query_failed', object=path, http_status=_status(exc)) from None
        if not isinstance(response, dict) or not isinstance(response.get(path), dict):
            raise AdmissionError('permission_evidence_insufficient', object=path)
        grants = response[path]
        for name, value in grants.items():
            if not isinstance(name, str) or type(value) not in (int, bool) or value not in (0, 1):
                raise AdmissionError('permission_value_invalid', object=path)
        return grants

    def require(self, path: str, privileges: list[str] | tuple[str, ...], *, operation: str = 'access') -> dict:
        grants = self.grants(path)
        missing = [name for name in privileges if name not in grants]
        if missing:
            raise AdmissionError('permission_missing', object=path, operation=operation, missing_privileges=missing)
        return grants

    def pool(self, pool: str) -> dict:
        if not pool:
            raise AdmissionError('pool_required', operation='placement')
        path = '/api2/json/pools/' + quote(pool, safe='')
        try:
            if hasattr(self.client, 'pool_detail'):
                response = self.client.pool_detail(pool)
            else:
                response = self.client.request('GET', path)
        except Exception as exc:
            code = 'pool_not_found' if _status(exc) == 404 else 'permission_query_failed'
            raise AdmissionError(code, object='/pool/' + pool, operation='placement', http_status=_status(exc)) from None
        if not isinstance(response, dict) or not isinstance(response.get('members'), list):
            raise AdmissionError('permission_evidence_insufficient', object='/pool/' + pool)
        return response

    def placement(self, vmid: int, pool: str | None, privileges: list[str] | tuple[str, ...],
                  *, future: bool = True) -> dict:
        """Native allocation OR, without synthesizing future grants by ACL union.

        A nonempty direct effective set excludes NoAccess for both principal and
        token. Complete effective pool grants can then supply the whole required
        set through PVE pool inheritance. Empty direct evidence is ambiguous.
        """
        path = f'/vms/{vmid}'
        direct = self.grants(path)
        pooled = self.grants('/pool/' + pool) if pool else {}
        if (future or 'VM.Allocate' in privileges) and 'VM.Allocate' not in direct and 'VM.Allocate' not in pooled:
            raise AdmissionError('permission_missing', object=path, operation='allocate', missing_privileges=['VM.Allocate'])
        lifecycle = [name for name in privileges if name != 'VM.Allocate']
        if all(name in direct for name in lifecycle):
            return {'permission_path': path, 'prospective': future}
        if future and pooled and all(name in pooled for name in lifecycle):
            if not direct:
                raise AdmissionError('permission_evidence_insufficient', object=path, operation='prospective_pool_membership')
            return {'permission_path': '/pool/' + str(pool), 'prospective': True}
        raise AdmissionError('permission_missing', object=path, operation='lifecycle',
                             missing_privileges=[name for name in lifecycle if name not in direct])


def require_free_vmid(vmid: int, snapshot: dict, *, node: str, cluster_nodes: list[str]) -> None:
    if (not isinstance(snapshot, dict) or snapshot.get('complete') is not True
            or snapshot.get('local_node') != node or not cluster_nodes
            or not isinstance(snapshot.get('nodes'), list) or set(snapshot['nodes']) != set(cluster_nodes)
            or not isinstance(snapshot.get('vmids'), list)
            or any(type(value) is not int or value <= 0 for value in snapshot['vmids'])):
        raise AdmissionError('permission_evidence_insufficient', object=f'/vms/{vmid}', operation='occupancy')
    if vmid in snapshot['vmids']:
        raise AdmissionError('vmid_occupied', object=f'/vms/{vmid}', operation='occupancy')


def require_helper_capabilities(declaration: Any, helper: str) -> None:
    required = {'upload': ('acceptance', 'create_only', 'verify', 'deadline'),
                'delete': ('inspect', 'exact_delete', 'reference', 'digest', 'deadline')}[helper]
    if not isinstance(declaration, dict) or declaration.get('helper') != helper:
        raise AdmissionError('helper_unavailable', object=helper, operation='capabilities')
    capabilities = declaration.get('capabilities')
    if (declaration.get('schema_version') != 'helper-capabilities/v1'
            or declaration.get('protocol_version') != 2 or not isinstance(capabilities, dict)
            or any(capabilities.get(name) is not True for name in required)):
        raise AdmissionError('helper_capability_missing', object=helper, operation='capabilities')


def disk_capacity(client: Any, config: dict, owner: dict, limit: int) -> dict:
    """Include clone-owned cloud-init/EFI/TPM disks; refuse unknown sizes."""
    disks = []
    for slot, value in config.items():
        if not re.fullmatch(r'(?:scsi|virtio|sata|ide|efidisk|tpmstate|unused)\d+', slot):
            continue
        value = str(value)
        if 'media=cdrom' in value and 'cloudinit' not in value:
            continue
        volume = value.split(',', 1)[0]
        match = re.search(r'(?:^|,)size=(\d+(?:\.\d+)?)([KMGT]?)B?(?:,|$)', value)
        if match:
            size = int(Decimal(match[1]) * 1024 ** (' KMGT'.index(match[2]) if match[2] else 0))
        else:
            storage = volume.split(':', 1)[0]
            try:
                rows = client.request('GET', f"/api2/json/nodes/{quote(owner['node'], safe='')}/storage/{quote(storage, safe='')}/content")
            except Exception:
                raise AdmissionError('disk_size_unknown', object=slot) from None
            matches = [row for row in rows if isinstance(row, dict) and row.get('volid') == volume] if isinstance(rows, list) else []
            if len(matches) != 1 or str(matches[0].get('vmid')) != str(owner['vmid']):
                raise AdmissionError('disk_size_unknown', object=slot)
            size = matches[0].get('size')
        if type(size) is not int or size <= 0:
            raise AdmissionError('disk_size_unknown', object=slot)
        disks.append({'slot': slot, 'required_bytes': size})
    capacity = {'disk_limit_bytes': limit, 'total_required_bytes': sum(row['required_bytes'] for row in disks), 'disks': disks}
    if not disks:
        raise AdmissionError('disk_size_unknown', capacity=capacity)
    if capacity['total_required_bytes'] > limit:
        raise AdmissionError('disk_limit_exceeded', capacity=capacity)
    return capacity


ACCEPTANCE_PRIVILEGES = ('VM.Audit', 'VM.Allocate', 'VM.Config.CPU', 'VM.Config.Memory',
                         'VM.Config.Disk', 'VM.Config.Network', 'VM.Config.Options',
                         'VM.Config.HWType', 'VM.Config.Cloudinit', 'VM.PowerMgmt',
                         'VM.GuestAgent.Unrestricted')


def admit_acceptance(client: Any, request: dict, *, helpers: Any) -> dict:
    """GET-only admission; helpers must supply capabilities(name) and inspect().

    The transport must already enforce isolated key/trust and fixed SSH target.
    Its successful sudo probes establish availability; inspect ties that SSH
    target's local node and complete pmxcfs scope to the selected API cluster.
    """
    vm, record = request['temporary_vm'], request['template_record']
    permissions = Permissions(client)
    pool = vm.get('pool')
    permissions.pool(pool)
    permissions.require(f"/vms/{record['vmid']}", ('VM.Audit', 'VM.Clone'), operation='source_clone')
    placement = permissions.placement(vm['vmid'], pool, ACCEPTANCE_PRIVILEGES)
    nodepath = '/api2/json/nodes/' + quote(vm['node'], safe='')
    permissions.require('/nodes/' + vm['node'], ('Sys.Audit',), operation='node_status')

    def get(path: str, reason: str) -> Any:
        try:
            return client.request('GET', path)
        except Exception as exc:
            raise AdmissionError(reason, object=path, http_status=_status(exc)) from None

    cluster = get('/api2/json/cluster/status', 'permission_query_failed')
    nodes = [row.get('name') for row in cluster if isinstance(row, dict) and row.get('type') == 'node'] if isinstance(cluster, list) else []
    if not nodes or any(not isinstance(name, str) for name in nodes):
        raise AdmissionError('permission_evidence_insufficient', operation='cluster_scope')
    nodes = cast(list[str], nodes)
    if not any(row.get('name') == vm['node'] and row.get('online') in (1, True) for row in cluster):
        raise AdmissionError('node_unavailable', object=vm['node'])
    status = get(nodepath + '/status', 'node_unavailable')
    if (not isinstance(status, dict) or not isinstance(status.get('cpuinfo'), dict)
            or not isinstance(status.get('memory'), dict)
            or type(status['cpuinfo'].get('cpus')) is not int or type(status['memory'].get('total')) is not int):
        raise AdmissionError('resource_evidence_insufficient', object=vm['node'])
    if vm['cpus'] > status['cpuinfo']['cpus'] or vm['memory_mib'] * 1024 ** 2 > status['memory']['total']:
        raise AdmissionError('resource_limit_exceeded', object=vm['node'])
    source = get(f"/api2/json/nodes/{quote(record['node'], safe='')}/qemu/{record['vmid']}/config", 'source_query_failed')
    if not isinstance(source, dict):
        raise AdmissionError('source_evidence_insufficient')
    stable = lambda config: {key: value for key, value in config.items() if key not in {'digest', 'lock'}}
    if (stable(source) != stable(record['configuration']) or pve._config_uuid(source) != record['smbios_uuid']
            or source.get('template') not in (1, '1') or pve.template_identity(source)['disks'] != record['volumes']):
        raise AdmissionError('source_changed')
    if (source.get('hookscript') or source.get('args')
            or any(re.fullmatch(r'(hostpci|usb|unused)\d+', key) for key in source)):
        raise AdmissionError('source_has_unbounded_devices')
    if vm['boot'] not in pve._disk_slots(source):
        raise AdmissionError('boot_disk_missing')
    firmware = 'uefi' if source.get('bios') == 'ovmf' else 'bios'
    if firmware != vm['firmware']:
        raise AdmissionError('disk_boot_mismatch')
    capacity = disk_capacity(client, source, record, vm['disk_limit_bytes'])
    for storage, content in ((vm['storage'], 'images'), (request['cloud_init']['snippet_storage'], 'snippets')):
        permissions.require('/storage/' + storage, ('Datastore.Audit', 'Datastore.AllocateSpace'), operation='storage')
        info = get(nodepath + '/storage/' + quote(storage, safe='') + '/status', 'storage_unavailable')
        if (not isinstance(info, dict) or info.get('enabled') not in (1, True) or info.get('active') not in (1, True)
                or content not in str(info.get('content', '')).split(',') or not isinstance(info.get('type'), str)):
            raise AdmissionError('storage_unavailable', object=storage)
        if content == 'images':
            if type(info.get('avail')) is not int:
                raise AdmissionError('storage_capacity_insufficient', object=storage, capacity=capacity)
            capacity['storage_available_bytes'] = info['avail']
            if capacity['total_required_bytes'] > info['avail']:
                raise AdmissionError('storage_capacity_insufficient', object=storage, capacity=capacity)
    network = get(nodepath + '/network', 'network_unavailable')
    bridges = [row for row in network if isinstance(row, dict) and row.get('iface') == vm['bridge']] if isinstance(network, list) else []
    if len(bridges) != 1 or bridges[0].get('type') not in ('bridge', 'OVSBridge') or bridges[0].get('active') not in (1, True):
        raise AdmissionError('network_unavailable', object=vm['bridge'])
    if vm.get('vlan_tag') and bridges[0].get('bridge_vlan_aware') not in (1, True):
        raise AdmissionError('network_unavailable', object=vm['bridge'])
    networks = [(vm['bridge'], vm.get('vlan_tag'))]
    for key, value in source.items():
        if re.fullmatch(r'net\d+', key):
            fields = dict(part.split('=', 1) for part in str(value).split(',') if '=' in part)
            if fields.get('bridge'):
                networks.append((fields['bridge'], fields.get('tag')))
    for bridge, tag in networks:
        path = '/sdn/zones/localnetwork/' + bridge + ('/' + str(tag) if tag else '')
        permissions.require(path, ('SDN.Use',), operation='network_attach')
    try:
        for helper in ('upload', 'delete'):
            require_helper_capabilities(helpers.capabilities(helper), helper)
        snapshot = helpers.inspect()
    except AdmissionError:
        raise
    except Exception:
        raise AdmissionError('helper_unavailable', operation='readonly_probe') from None
    require_free_vmid(vm['vmid'], snapshot, node=vm['node'], cluster_nodes=nodes)
    return {'source_snapshot': source, 'capacity': capacity,
            'readiness': {'status': 'ready', 'pool': pool, 'vmid_free': True,
                          'helpers': 'ready', 'cluster_nodes': sorted(nodes), **placement}}
