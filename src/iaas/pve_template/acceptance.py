"""One full-clone technical acceptance, with independent bounded cleanup."""
from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from typing import Any
from urllib.parse import quote

from iaas.common.errors import ValidationError, require
from iaas.pve_acceptance_contracts import canonical_digest, load_strict_json, validate_acceptance_request, validate_acceptance_result
from iaas.runtime_execution.execution import OperationFailed
from . import runtime as pve
from .acceptance_execution import begin, observe, save

CHECKS = ('full_clone', 'disk_boot', 'guest_agent', 'cloud_init', 'injected_hostname', 'source_unchanged')


class UnknownOutcome(OperationFailed):
    """A mutation or observation cannot be established from original evidence."""


class AcceptanceFailure(OperationFailed):
    """A known negative check, including a bounded guest deadline."""


def stable(config: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in config.items() if key not in {'digest', 'lock'}}


def check(condition: Any, reason: str) -> None:
    if not condition:
        raise AcceptanceFailure(reason)


def attachments(config: dict[str, Any]) -> dict[str, str]:
    # Cloud-init disks use media=cdrom but are clone-owned generated volumes.
    return {key: str(value).split(',', 1)[0] for key, value in config.items()
            if re.fullmatch(r'(?:scsi|virtio|sata|ide|efidisk|tpmstate|unused)\d+', key)
            and ('media=cdrom' not in str(value) or 'cloudinit' in str(value))}


class Acceptance:
    def __init__(self, client: Any, request: dict[str, Any], journal: dict[str, Any], root: Path) -> None:
        self.client, self.request, self.journal, self.root = client, request, journal, root
        self.temporary = request['temporary_vm']
        self.record = request['template_record']
        self.base = f"/api2/json/nodes/{quote(self.temporary['node'], safe='')}/qemu/{self.temporary['vmid']}"
        self.source = f"/api2/json/nodes/{quote(self.record['node'], safe='')}/qemu/{self.record['vmid']}"
        self.deadline = time.monotonic() + request['timeouts']['work_seconds']
        self.stage = 'full_clone'
        self.source_before: dict[str, Any] | None = None
        self.owned: dict[str, Any] | None = None
        self.remaining_volumes: list[str] | None = None
        self.result: dict[str, Any] = {}

    def persist(self) -> None:
        save(self.root / 'journal.json', self.journal)

    def api(self, method: str, path: str, **kwargs: Any) -> Any:
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise AcceptanceFailure('deadline_exceeded')
        self.client.timeout = min(30, remaining)
        return self.client.request(method, path, **kwargs)

    def mutation(self, phase: str, method: str, path: str, *, fields: dict[str, Any] | None = None,
                 task: bool = True, node: str | None = None) -> None:
        check(time.monotonic() < self.deadline, 'deadline_exceeded')
        item: dict[str, Any] = {'phase': phase, 'status': 'intent', 'node': node or self.temporary['node']}
        self.journal['tasks'].append(item)
        self.journal['mutation_active'] = True
        self.persist()
        try:
            value = self.api(method, path, fields=fields)
            if task:
                item['upid'] = pve._normalize_upid(value, item['node'])
                item['status'] = 'running'
                self.persist()
                self.wait_task(item)
            else:
                item['status'] = 'succeeded'
                self.journal['mutation_active'] = False
                self.persist()
        except AcceptanceFailure:
            raise
        except Exception:
            item['status'] = 'unknown'
            self.persist()
            raise UnknownOutcome('native_operation_unknown') from None

    def wait_task(self, item: dict[str, Any]) -> None:
        while time.monotonic() < self.deadline:
            row = self.api('GET', f"/api2/json/nodes/{quote(item['node'], safe='')}/tasks/{quote(item['upid'], safe='')}/status")
            if isinstance(row, dict) and row.get('status') == 'stopped':
                item['status'] = 'succeeded' if row.get('exitstatus') == 'OK' else 'failed'
                self.journal['mutation_active'] = False
                self.persist()
                check(item['status'] == 'succeeded', 'native_task_failed')
                return
            time.sleep(min(.2, max(0, self.deadline - time.monotonic())))
        raise UnknownOutcome('native_task_unknown')

    def vm_absent(self) -> bool:
        path = f"/vms/{self.temporary['vmid']}"
        grants = self.api('GET', '/api2/json/access/permissions', fields={'path': path})
        check(isinstance(grants, dict) and isinstance(grants.get(path), dict)
              and type(grants[path].get('VM.Audit')) in {int, bool}
              and grants[path]['VM.Audit'] in (0, 1), 'vm_visibility_unproven')
        rows = self.api('GET', '/api2/json/cluster/resources', fields={'type': 'vm'})
        check(isinstance(rows, list) and all(isinstance(row, dict) and 'vmid' in row for row in rows),
              'vm_inventory_incomplete')
        return not any(str(row['vmid']) == str(self.temporary['vmid']) for row in rows)

    def source_check(self, *, initial: bool) -> None:
        config = self.api('GET', self.source + '/config')
        check(isinstance(config, dict), 'source_config_invalid')
        expected = self.record['configuration'] if initial else self.source_before
        check(expected is not None and stable(config) == stable(expected)
              and pve._config_uuid(config) == self.record['smbios_uuid']
              and config.get('template') in (1, '1'), 'source_changed')
        if initial:
            check(pve._disk_slots(config) == self.record['volumes'], 'source_volumes_changed')
            check(not config.get('hookscript') and not any(re.fullmatch(r'(hostpci|usb|unused)\d+', key) for key in config),
                  'source_has_unbounded_devices')
            check(not config.get('args'), 'source_has_unbounded_devices')
            check(self.temporary['boot'] in pve._disk_slots(config), 'boot_disk_missing')
            self.disk_bound(config)
            self.source_before = config
            self.journal['source_before'] = config
            self.persist()

    def storage_permissions(self) -> None:
        path = '/storage/' + self.temporary['storage']
        permissions = self.api('GET', '/api2/json/access/permissions', fields={'path': path})
        grants = permissions.get(path) if isinstance(permissions, dict) else None
        # PVE maps granted privileges to propagation flags (both 0 and 1 are grants).
        check(isinstance(grants, dict) and all(type(grants.get(name)) in {int, bool}
              and grants[name] in (0, 1) for name in ('Datastore.Audit', 'Datastore.AllocateSpace')),
              'storage_permissions_incomplete')

    def disk_bound(self, config: dict[str, Any]) -> None:
        total = 0
        for slot in attachments(config):
            value = str(config[slot])
            match = re.search(r'(?:^|,)size=(\d+(?:\.\d+)?)([KMGT]?)B?(?:,|$)', value)
            check(match is not None, 'disk_size_unknown')
            assert match is not None
            total += int(float(match[1]) * 1024 ** (' KMGT'.index(match[2]) if match[2] else 0))
        check(0 < total <= self.temporary['disk_limit_bytes'], 'disk_limit_exceeded')

    def claim(self) -> dict[str, Any]:
        config = self.api('GET', self.base + '/config')
        check(isinstance(config, dict) and config.get('template', 0) in (0, '0'), 'clone_identity_invalid')
        identity = pve._config_uuid(config)
        volumes = attachments(config)
        source_volumes = set(attachments(self.source_before or {}).values())
        check(identity and identity != self.record['smbios_uuid'] and volumes
              and not source_volumes.intersection(volumes.values()), 'clone_ownership_unproven')
        check(all(volid.startswith(self.temporary['storage'] + ':') for volid in volumes.values()),
              'clone_storage_mismatch')
        rows = self.api('GET', f"/api2/json/nodes/{quote(self.temporary['node'], safe='')}/storage/{quote(self.temporary['storage'], safe='')}/content")
        check(isinstance(rows, list), 'volume_inventory_incomplete')
        indexed = {row.get('volid'): row for row in rows if isinstance(row, dict)}
        check(all(str(indexed.get(volid, {}).get('vmid')) == str(self.temporary['vmid']) for volid in volumes.values()),
              'clone_volume_ownership_unproven')
        self.owned = {'node': self.temporary['node'], 'vmid': self.temporary['vmid'],
                      'smbios_uuid': identity, 'volumes': sorted(volumes.values())}
        self.journal['temporary_vm'] = self.owned
        self.journal['snippets'] = []
        self.persist()
        return config

    def configure(self, config: dict[str, Any]) -> None:
        vm = self.temporary
        fields = {'name': self.request['cloud_init']['hostname'], 'cores': vm['cpus'], 'sockets': 1,
                  'memory': vm['memory_mib'], 'agent': 'enabled=1', 'onboot': 0,
                  'boot': 'order=' + vm['boot'], 'net0': f"virtio,bridge={vm['bridge']}",
                  'ipconfig0': vm['ip_config'], 'digest': config.get('digest', '')}
        if vm['vlan_tag'] is not None:
            fields['net0'] += f",tag={vm['vlan_tag']}"
        delete = [key for key in config if (re.fullmatch(r'(net|ipconfig)\d+', key) and key not in {'net0', 'ipconfig0'})
                  or key in {'cicustom', 'nameserver', 'searchdomain', 'cipassword', 'sshkeys'}]
        if delete:
            fields['delete'] = ','.join(sorted(delete))
        self.mutation('configure', 'PUT', self.base + '/config', fields=fields, task=False)
        actual = self.api('GET', self.base + '/config')
        self.identity(actual)
        self.disk_bound(actual)
        check(actual.get('boot') == 'order=' + vm['boot']
              and int(actual.get('cores', 0)) == vm['cpus'] and int(actual.get('sockets', 1)) == 1
              and int(actual.get('memory', 0)) == vm['memory_mib']
              and actual.get('bios', 'seabios') == ('ovmf' if vm['firmware'] == 'uefi' else 'seabios')
              and actual.get('name') == self.request['cloud_init']['hostname']
              and actual.get('ipconfig0') == vm['ip_config']
              and f"bridge={vm['bridge']}" in str(actual.get('net0', '')).split(',')
              and (vm['vlan_tag'] is None or f"tag={vm['vlan_tag']}" in str(actual.get('net0', '')).split(','))
              and not any(re.fullmatch(r'(net|ipconfig)\d+', key) and key not in {'net0', 'ipconfig0'} for key in actual)
              and not actual.get('cicustom')
              and any('cloudinit' in str(value) for value in actual.values()), 'disk_boot_mismatch')

    def identity(self, config: Any) -> None:
        check(isinstance(config, dict) and self.owned is not None
              and pve._config_uuid(config) == self.owned['smbios_uuid']
              and sorted(attachments(config).values()) == self.owned['volumes']
              and not config.get('lock') and config.get('template', 0) in (0, '0'), 'temporary_identity_changed')

    def guest(self) -> None:
        guest_deadline = min(self.deadline, time.monotonic() + self.request['timeouts']['guest_seconds'])
        self.deadline = guest_deadline
        self.stage = 'guest_agent'
        while True:
            try:
                self.api('POST', self.base + '/agent/ping')
                break
            except OperationFailed:
                if time.monotonic() >= guest_deadline:
                    raise AcceptanceFailure('guest_timeout') from None
                time.sleep(.2)
        self.mark('guest_agent', 'passed', 'verified')
        self.stage = 'cloud_init'
        while time.monotonic() < guest_deadline:
            # JSON body preserves the API's array command type; no shell or caller program.
            process = self.api('POST', self.base + '/agent/exec',
                               body=json.dumps({'command': ['cloud-init', 'status', '--format', 'json']}).encode(),
                               content_type='application/json')
            check(isinstance(process, dict) and type(process.get('pid')) is int, 'guest_response_invalid')
            while True:
                status = self.api('GET', self.base + '/agent/exec-status', fields={'pid': process['pid']})
                check(isinstance(status, dict), 'guest_response_invalid')
                if status.get('exited') in (True, 1):
                    break
                if time.monotonic() >= guest_deadline:
                    raise AcceptanceFailure('guest_timeout')
                time.sleep(.2)
            save(self.root / 'cloud-init-status.json', status)
            check(not status.get('out-truncated') and status.get('exitcode') == 0, 'cloud_init_failed')
            try:
                cloud = json.loads(status.get('out-data', ''))
            except (ValueError, TypeError):
                raise AcceptanceFailure('cloud_init_unparseable') from None
            check(isinstance(cloud, dict), 'cloud_init_unparseable')
            if cloud.get('status') in {'running', 'not started'}:
                time.sleep(.2)
                continue
            check(cloud.get('status') == 'done' and cloud.get('extended_status') == 'done'
                  and cloud.get('errors') == [] and cloud.get('recoverable_errors') == {}
                  and str(cloud.get('boot_status_code', '')).startswith('enabled-'), 'cloud_init_failed')
            self.mark('cloud_init', 'passed', 'verified')
            break
        else:
            raise AcceptanceFailure('guest_timeout')
        self.stage = 'injected_hostname'
        hostname = self.api('GET', self.base + '/agent/get-host-name')
        save(self.root / 'hostname.json', hostname)
        check(isinstance(hostname, dict) and isinstance(hostname.get('result'), dict)
              and hostname['result'].get('host-name') == self.request['cloud_init']['hostname'], 'hostname_mismatch')
        self.mark('injected_hostname', 'passed', 'verified')

    def mark(self, name: str, status: str, reason: str) -> None:
        for item in self.result['checks']:
            if item['id'] == name:
                evidence = {'cloud_init': 'cloud-init-status.json', 'injected_hostname': 'hostname.json'}.get(name, 'journal.json')
                item.update(status=status, reason_code=reason,
                            evidence_ref=evidence if (self.root / evidence).is_file() else None)

    def cleanup(self) -> None:
        self.deadline = time.monotonic() + self.request['timeouts']['cleanup_seconds']
        cleanup = self.result['cleanup']
        if self.journal['mutation_active'] or (self.owned is None and self.journal['tasks']):
            raise UnknownOutcome('ownership_or_task_unknown')
        if self.owned is None:
            return
        self.identity(self.api('GET', self.base + '/config'))
        status = self.api('GET', self.base + '/status/current')
        check(isinstance(status, dict) and status.get('status') in {'running', 'stopped'}, 'vm_status_unknown')
        if status['status'] == 'running':
            self.mutation('stop', 'POST', self.base + '/status/stop')
        self.identity(self.api('GET', self.base + '/config'))
        self.mutation('delete', 'DELETE', self.base, fields={'purge': 0, 'destroy-unreferenced-disks': 0})
        check(self.vm_absent(), 'vm_still_present')
        cleanup['vm'] = {'status': 'passed', 'reason_code': 'deleted', 'evidence_ref': 'journal.json'}
        self.journal['vm_delete'] = {'status': 'deleted', 'execution_id': self.journal['execution_id'],
                                   **{k: v for k, v in self.owned.items() if k != 'volumes'},
                                   'upid': self.journal['tasks'][-1]['upid']}
        self.persist()
        rows = self.api('GET', f"/api2/json/nodes/{quote(self.temporary['node'], safe='')}/storage/{quote(self.temporary['storage'], safe='')}/content")
        check(isinstance(rows, list) and all(isinstance(row, dict) and 'volid' in row for row in rows),
              'volume_inventory_incomplete')
        self.remaining_volumes = sorted(set(self.owned['volumes']).intersection(row['volid'] for row in rows))
        check(not self.remaining_volumes, 'volumes_still_present')
        cleanup['volumes'] = {'status': 'passed', 'reason_code': 'deleted', 'evidence_ref': 'journal.json'}

    def execute(self) -> dict[str, Any]:
        self.result = {'kind': 'pve-template-acceptance-result', 'schema_version': 1,
            'execution_id': self.journal['execution_id'], 'request_digest': self.journal['request_digest'],
            'runtime': self.journal['runtime'],
            'template': {key: self.record[key] for key in ('record_id', 'execution_id', 'artifact_digest', 'node', 'vmid', 'smbios_uuid')},
            'temporary_resources': {},
            'checks': [{'id': name, 'status': 'not_attempted', 'reason_code': 'not_attempted', 'evidence_ref': None} for name in CHECKS],
            'failure_stage': None, 'cleanup': {name: {'status': 'not_required', 'reason_code': 'not_created', 'evidence_ref': None} for name in ('vm', 'volumes', 'snippets')},
            'residuals': {'inventory_complete': True, 'items': []}, 'overall': 'unknown', 'collection': {'status': 'complete', 'reason_code': 'collected'}}
        try:
            self.source_check(initial=True)
            check(self.vm_absent(), 'vmid_occupied')
            self.storage_permissions()
            self.mutation('clone', 'POST', self.source + '/clone',
                          fields={'newid': self.temporary['vmid'], 'full': 1, 'target': self.temporary['node'],
                                  'storage': self.temporary['storage'], 'name': self.request['cloud_init']['hostname']}, node=self.record['node'])
            config = self.claim()
            self.mark('full_clone', 'passed', 'verified')
            self.stage = 'disk_boot'
            self.configure(config)
            self.mark('disk_boot', 'passed', 'verified')
            self.mutation('start', 'POST', self.base + '/status/start')
            self.guest()
        except Exception as exc:
            unknown = not isinstance(exc, AcceptanceFailure) or self.journal['mutation_active']
            self.mark(self.stage, 'unknown' if unknown else 'failed',
                      str(exc) if isinstance(exc, AcceptanceFailure) else 'observation_unknown')
            self.result['failure_stage'] = self.stage
        finally:
            try:
                self.cleanup()
            except Exception as exc:
                status = 'failed' if isinstance(exc, AcceptanceFailure) and not self.journal['mutation_active'] else 'unknown'
                for name in ('vm', 'volumes'):
                    if self.result['cleanup'][name]['status'] != 'passed':
                        self.result['cleanup'][name] = {'status': status, 'reason_code': 'cleanup_incomplete', 'evidence_ref': 'journal.json'}
                resources = self.resources()
                self.result['residuals'] = {'inventory_complete': self.owned is not None,
                    'items': [{**resource, 'existence': 'present' if self.remaining_volumes is not None else 'unknown', 'reason_code': 'cleanup_incomplete'}
                              for resource in resources
                              if self.result['cleanup']['vm' if resource['kind'] == 'vm' else 'volumes']['status'] != 'passed'
                              and (self.remaining_volumes is None or resource['identity'] in self.remaining_volumes)]}
            try:
                self.source_check(initial=False)
                self.mark('source_unchanged', 'passed', 'verified')
            except Exception as exc:
                self.mark('source_unchanged', 'failed' if isinstance(exc, AcceptanceFailure) and str(exc) != 'deadline_exceeded' else 'unknown', 'source_recheck_failed')
        self.result['temporary_resources'] = self.resources()
        statuses = [item['status'] for item in self.result['checks']] + [item['status'] for item in self.result['cleanup'].values()]
        self.result['overall'] = ('unknown' if 'unknown' in statuses or any(x['existence'] == 'unknown' for x in self.result['residuals']['items']) or not self.result['residuals']['inventory_complete'] else 'passed'
                                  if all(item in {'passed', 'not_required'} for item in statuses) else 'failed')
        return validate_acceptance_result(self.result)

    def resources(self) -> list[dict[str, Any]]:
        if not self.journal['tasks']:
            return []
        common = {'node': self.temporary['node'], 'created_by': self.journal['execution_id'],
                  'ownership': 'owned' if self.owned else 'unknown'}
        return [{**common, 'kind': 'vm', 'identity': str(self.temporary['vmid'])}] + [
            {**common, 'kind': 'volume', 'identity': volume} for volume in (self.owned or {}).get('volumes', [])]


def run(selected: Any, operation: str, scope: str, execution: Any, image_digest: str, execution_id: str = '') -> None:
    mode = selected.options.get('execution_mode')
    if operation == 'read':
        mode = 'observe'
    require(mode in {'start', 'observe'}, 'explicit execution_mode start or observe is required')
    path = selected.files.get('acceptance_request')
    request = validate_acceptance_request(load_strict_json(Path(path))) if path else None
    if request is not None:
        require(not scope or scope == request['target']['node'], 'acceptance scope conflicts with target')
    root = execution.outputs.path('diagnostics') / 'execution'
    if mode == 'observe':
        original = selected.files.get('original_execution_dir')
        require(original, 'observe requires the original execution directory')
        original_root, output_root = Path(original).resolve(), execution.outputs.root.resolve()
        require(not output_root.is_relative_to(original_root) and not original_root.is_relative_to(output_root),
                'observe output must not overlap original execution evidence')
        try:
            journal, result = observe(Path(original), 'accept', request, execution_id)
        except (OSError, ValidationError, ValueError):
            execution.outputs.summary({'component': 'pve-template', 'operation': operation, 'status': 'failed', 'overall': 'unknown', 'reason_code': 'original_evidence_unavailable'})
            raise OperationFailed('original acceptance evidence unavailable or conflicting; no mutation performed') from None
        save(root / 'journal.json', journal)
        require(not scope or scope == journal['target']['node'], 'observation scope conflicts')
        if result is None:
            execution.outputs.summary({'component': 'pve-template', 'operation': operation,
                                       'status': 'failed', 'overall': 'unknown', 'reason_code': 'original_result_missing'})
            raise OperationFailed('original acceptance result is incomplete; no mutation performed')
    else:
        require(request is not None, 'acceptance_request is required')
        admission_path = selected.files.get('execution_admission')
        admission = load_strict_json(Path(admission_path)) if admission_path else selected.options.get('admission')
        journal = begin(root, 'accept', request, admission, execution_id, image_digest)
        ca_file = execution.environ.get('PVE_API_CA')
        if ca_file:
            trust = root / 'trust'
            trust.mkdir(mode=0o700)
            descriptor = os.open(trust / 'api-ca.pem', os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(descriptor, 'wb') as output:
                output.write(Path(ca_file).read_bytes())
                output.flush()
                os.fsync(output.fileno())
        client = pve._client(selected, execution, request['target'])
        if ca_file:
            # Publisher client loads the caller CA; retain the system roots too.
            client.context.load_default_certs()
        result = Acceptance(client, request, journal, root).execute()
        journal.update(status='finished', result_digest=canonical_digest(result))
        save(root / 'journal.json', journal)
    save(root / 'result.json', result)
    save(execution.outputs.path('diagnostics') / 'result.json', result)
    if result['overall'] != 'passed':
        raise OperationFailed('template acceptance did not pass; inspect protected result')
    execution.finish({'component': 'pve-template', 'operation': operation, 'execution_id': result['execution_id'],
                      'overall': result['overall'], 'request_digest': result['request_digest']})
