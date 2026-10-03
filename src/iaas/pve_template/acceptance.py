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
from . import acceptance_snippets
from .deadlines import DeadlineBudget, DeadlineExpired, LocalTimeout
from .responses import RequestRejected, RequestOutcomeUnknown
from .guest_observation import GENERAL_GUEST_OBSERVATION
from .admission import AdmissionError, Permissions, ACCEPTANCE_PRIVILEGES, admit_acceptance, disk_capacity
from .acceptance_plan import ReadBudgetClient

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
    def __init__(self, client: Any, request: dict[str, Any], journal: dict[str, Any], root: Path, snippets: Any = None,
                 budget: DeadlineBudget | None = None) -> None:
        self.client, self.request, self.journal, self.root = client, request, journal, root
        self.temporary = request['temporary_vm']
        self.record = request['template_record']
        self.base = f"/api2/json/nodes/{quote(self.temporary['node'], safe='')}/qemu/{self.temporary['vmid']}"
        self.source = f"/api2/json/nodes/{quote(self.record['node'], safe='')}/qemu/{self.record['vmid']}"
        self.budget = budget or DeadlineBudget(request['deadlines'])
        self.budget.limit('work', request['timeouts']['work_seconds'])
        self.phase = 'work'
        self.deadline = min(self.budget.bounds['work'], self.budget.local['work'])
        self.stage = 'full_clone'
        self.source_before: dict[str, Any] | None = None
        self.owned: dict[str, Any] | None = None
        self.remaining_volumes: list[str] | None = None
        self.result: dict[str, Any] = {}
        self.snippets = snippets
        if snippets is not None:
            snippets.budget, snippets.phase, snippets.deadline = self.budget, self.phase, self.deadline

    def upload_user_data(self) -> dict:
        self.remaining()
        check(self.snippets is not None, 'snippet_transport_missing')
        self.snippets.budget, self.snippets.phase = self.budget, self.phase
        self.snippets.deadline = self.deadline
        snapshot = self.snippets.inspect()
        check(snapshot.get('complete') is True and snapshot.get('local_node') == self.temporary['node'],
              'snippet_scope_unconfirmed')
        content = acceptance_snippets.user_data(self.request)
        snippet = acceptance_snippets.record(self.request, content)
        self.journal['snippets'] = [snippet]
        self.journal['mutation_active'] = True
        previous_writes = self.journal['facility_writes']
        self.journal['facility_writes'] = 'unknown'
        self.persist()
        self.snippets.deadline = self.deadline
        self.snippets.budget, self.snippets.phase = self.budget, self.phase
        try:
            self.remaining()
        except (DeadlineExpired, LocalTimeout):
            self.journal.update(mutation_active=False, facility_writes=previous_writes)
            self.persist()
            raise
        self.snippets.upload(snippet, content)
        self.journal['facility_writes'] = 'issued'
        snippet['uploaded'] = True
        self.journal['mutation_active'] = False
        self.persist()
        return snippet

    def cleanup_snippets(self) -> None:
        records = self.journal.get('snippets', [])
        if not records:
            return
        check(not self.journal['mutation_active'] and all(s['uploaded'] for s in records)
              and self.result['cleanup']['vm']['status'] == 'passed', 'snippet_ownership_unconfirmed')
        self.snippets.deadline = self.deadline
        self.snippets.budget, self.snippets.phase = self.budget, self.phase
        snapshot = self.snippets.inspect()
        check(snapshot.get('complete') is True and snapshot.get('local_node') == self.temporary['node']
              and snapshot.get('reference_strategy') == 'all_storage_aliases_by_filename'
              and isinstance(snapshot.get('vmids'), list) and isinstance(snapshot.get('references'), list)
              and self.temporary['vmid'] not in snapshot['vmids'], 'snippet_scope_unconfirmed')
        self.snippets.original_vmid = self.temporary['vmid']
        for snippet in records:
            self.remaining()
            check(snippet['file_name'] not in snapshot['references'], 'snippet_still_referenced')
            self.journal['mutation_active'] = True
            previous_writes = self.journal['facility_writes']
            self.journal['facility_writes'] = 'unknown'
            self.persist()
            try:
                self.remaining()
            except (DeadlineExpired, LocalTimeout):
                self.journal.update(mutation_active=False, facility_writes=previous_writes)
                self.persist()
                raise
            answer = self.snippets.delete(snippet)
            self.journal['facility_writes'] = 'issued'
            self.journal['mutation_active'] = False
            snippet['cleanup'] = answer
            self.persist()
            check(answer.get('status') in {'deleted', 'already_absent'}, 'snippet_cleanup_failed')
        self.result['cleanup']['snippets'] = {'status': 'passed', 'reason_code': 'deleted', 'evidence_ref': 'journal.json'}

    def persist(self) -> None:
        self.journal['deadline_outcome'] = dict(self.budget.outcome)
        save(self.root / 'journal.json', self.journal)

    def api(self, method: str, path: str, **kwargs: Any) -> Any:
        remaining = self.remaining()
        self.client.timeout = min(30, remaining)
        return self.client.request(method, path, **kwargs)

    def remaining(self) -> float:
        return self.budget.remaining(self.phase)

    def pause(self) -> None:
        time.sleep(min(.2, self.remaining()))

    def mutation(self, phase: str, method: str, path: str, *, fields: dict[str, Any] | None = None,
                 task: bool = True, node: str | None = None) -> None:
        self.remaining()
        item: dict[str, Any] = {'phase': phase, 'status': 'intent', 'node': node or self.temporary['node'],
                                'method': method, 'path': path}
        self.journal['tasks'].append(item)
        previous_active = self.journal['mutation_active']
        self.journal['mutation_active'] = True
        previous_writes = self.journal['facility_writes']
        self.journal['facility_writes'] = 'unknown'
        self.persist()
        try:
            try:
                self.remaining()
                value = self.api(method, path, fields=fields)
            except RequestRejected as exc:
                item.update(status='rejected', http_status=exc.http_status)
                self.journal.update(mutation_active=previous_active, facility_writes=previous_writes)
                self.persist()
                raise AcceptanceFailure('request_rejected') from None
            except (DeadlineExpired, LocalTimeout):
                item['status'] = 'not_sent'
                self.journal.update(mutation_active=False, facility_writes=previous_writes)
                self.persist()
                raise
            self.journal['facility_writes'] = 'issued'
            if task:
                item['upid'] = pve._normalize_upid(value, item['node'])
                item['status'] = 'running'
                self.persist()
                self.wait_task(item)
            else:
                item['status'] = 'succeeded'
                self.journal['mutation_active'] = False
                self.persist()
        except (AcceptanceFailure, DeadlineExpired, LocalTimeout):
            raise
        except Exception:
            item['status'] = 'unknown'
            self.persist()
            raise UnknownOutcome('native_operation_unknown') from None

    def wait_task(self, item: dict[str, Any]) -> None:
        while True:
            try:
                self.remaining()
            except (DeadlineExpired, LocalTimeout):
                raise UnknownOutcome('native_task_unknown') from None
            row = self.api('GET', f"/api2/json/nodes/{quote(item['node'], safe='')}/tasks/{quote(item['upid'], safe='')}/status")
            if isinstance(row, dict) and row.get('status') == 'stopped':
                item['status'] = 'succeeded' if row.get('exitstatus') == 'OK' else 'failed'
                self.journal['mutation_active'] = False
                self.persist()
                check(item['status'] == 'succeeded', 'native_task_failed')
                return
            self.pause()

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
        if not initial and self.source_before is None:
            raise UnknownOutcome('source_snapshot_missing')
        try:
            config = self.api('GET', self.source + '/config')
        except (DeadlineExpired, LocalTimeout):
            raise
        except Exception:
            raise UnknownOutcome('source_query_failed') from None
        if not isinstance(config, dict):
            raise UnknownOutcome('source_evidence_insufficient')
        expected = self.record['configuration'] if initial else self.source_before
        check(expected is not None and stable(config) == stable(expected)
              and pve._config_uuid(config) == self.record['smbios_uuid']
              and config.get('template') in (1, '1'), 'source_changed')
        if initial:
            check(pve.template_identity(config)['disks'] == self.record['volumes'], 'source_volumes_changed')
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
        owner = self.record if config.get('template') in (1, '1') else self.temporary
        disk_capacity(self.client, config, owner, self.temporary['disk_limit_bytes'])

    def pool_check(self) -> None:
        rows = self.api('GET', '/api2/json/cluster/resources', fields={'type': 'vm'})
        check(isinstance(rows, list), 'pool_membership_mismatch')
        matches = [row for row in rows if isinstance(row, dict)
                   and str(row.get('vmid')) == str(self.temporary['vmid'])]
        check(len(matches) == 1 and matches[0].get('node') == self.temporary['node']
              and matches[0].get('pool') == self.temporary['pool'], 'pool_membership_mismatch')
        Permissions(self.client).placement(self.temporary['vmid'], self.temporary['pool'],
                                           ACCEPTANCE_PRIVILEGES, future=False)

    def claim(self) -> dict[str, Any]:
        self.pool_check()
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
        if vm.get('disk_size_gib') is not None:
            self.identity(config)
            self.mutation('resize', 'PUT', self.base + '/resize',
                          fields={'disk': vm['boot'], 'size': f"{vm['disk_size_gib']}G"})
            config = self.api('GET', self.base + '/config')
            self.identity(config)
            capacity = disk_capacity(self.client, config, vm, vm['disk_limit_bytes'])
            actual_size = next(row['required_bytes'] for row in capacity['disks'] if row['slot'] == vm['boot'])
            check(actual_size == vm['disk_size_gib'] * 1024 ** 3, 'disk_resize_mismatch')
        snippet = self.upload_user_data()
        fields = {'name': self.request['cloud_init']['hostname'], 'cores': vm['cpus'], 'sockets': 1,
                  'memory': vm['memory_mib'], 'agent': 'enabled=1', 'onboot': 0,
                  'boot': 'order=' + vm['boot'], 'net0': f"virtio,bridge={vm['bridge']}",
                  'ipconfig0': vm['ip_config'], 'digest': config.get('digest', ''),
                  'cicustom': 'user=' + snippet['file_id']}
        if vm['vlan_tag'] is not None:
            fields['net0'] += f",tag={vm['vlan_tag']}"
        if vm.get('nameservers') is not None:
            fields['nameserver'] = ' '.join(vm['nameservers'])
        delete = [key for key in config if (re.fullmatch(r'(net|ipconfig)\d+', key) and key not in {'net0', 'ipconfig0'})
                  or key in {'nameserver', 'searchdomain', 'cipassword', 'sshkeys'}]
        if vm.get('nameservers') is not None and 'nameserver' in delete:
            delete.remove('nameserver')
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
              and actual.get('cicustom') == 'user=' + snippet['file_id']
              and any('cloudinit' in str(value) for value in actual.values()), 'disk_boot_mismatch')
        if vm.get('nameservers') is not None:
            check(str(actual.get('nameserver', '')).split() == vm['nameservers'], 'network_configuration_mismatch')

    def identity(self, config: Any) -> None:
        self.pool_check()
        check(isinstance(config, dict) and self.owned is not None
              and pve._config_uuid(config) == self.owned['smbios_uuid']
              and sorted(attachments(config).values()) == self.owned['volumes']
              and not config.get('lock') and config.get('template', 0) in (0, '0'), 'temporary_identity_changed')

    def guest(self) -> None:
        self.budget.limit('work', self.request['timeouts']['guest_seconds'])
        guest_deadline = min(self.budget.bounds['work'], self.budget.local['work'])
        self.deadline = guest_deadline
        self.stage = 'guest_agent'
        while True:
            try:
                self.api('POST', self.base + '/agent/ping')
                break
            except RequestRejected:
                raise AcceptanceFailure('request_rejected') from None
            except OperationFailed:
                if time.monotonic() >= guest_deadline:
                    raise AcceptanceFailure('guest_timeout') from None
                self.pause()
        self.mark('guest_agent', 'passed', 'verified')
        self.stage = 'cloud_init'
        while time.monotonic() < guest_deadline:
            # JSON body preserves the API's array command type; no shell or caller program.
            self.remaining()
            intent: dict[str, Any] = {'phase': 'guest_exec', 'status': 'intent', 'method': 'POST',
                                    'path': self.base + '/agent/exec'}
            self.journal['tasks'].append(intent)
            previous_active = self.journal['mutation_active']
            self.journal['mutation_active'] = True
            previous_writes = self.journal['facility_writes']
            self.journal['facility_writes'] = 'unknown'
            self.persist()
            try:
                command = ['cloud-init', 'status', '--format', 'json']
                if self.temporary.get('disk_size_gib') is not None or self.temporary.get('nameservers') is not None:
                    command = ['python3', '-c', GENERAL_GUEST_OBSERVATION]
                process = self.api('POST', self.base + '/agent/exec',
                                   body=json.dumps({'command': command}).encode(),
                                   content_type='application/json')
            except RequestRejected as exc:
                intent.update(status='rejected', http_status=exc.http_status)
                self.journal.update(mutation_active=previous_active, facility_writes=previous_writes)
                self.persist()
                raise AcceptanceFailure('request_rejected') from None
            except (DeadlineExpired, LocalTimeout):
                intent['status'] = 'not_sent'
                self.journal.update(mutation_active=False, facility_writes=previous_writes)
                self.persist()
                raise
            except Exception:
                intent['status'] = 'unknown'
                self.persist()
                raise UnknownOutcome('request_outcome_unknown') from None
            check(isinstance(process, dict) and type(process.get('pid')) is int, 'guest_response_invalid')
            intent.update(status='running', pid=process['pid'])
            self.journal['facility_writes'] = 'issued'
            self.persist()
            while True:
                status = self.api('GET', self.base + '/agent/exec-status', fields={'pid': process['pid']})
                check(isinstance(status, dict), 'guest_response_invalid')
                if status.get('exited') in (True, 1):
                    intent['status'] = 'succeeded' if status.get('exitcode') == 0 else 'failed'
                    self.journal['mutation_active'] = False
                    self.persist()
                    break
                if time.monotonic() >= guest_deadline:
                    raise AcceptanceFailure('guest_timeout')
                self.pause()
            save(self.root / 'cloud-init-status.json', status)
            check(not status.get('out-truncated') and status.get('exitcode') == 0, 'cloud_init_failed')
            try:
                cloud = json.loads(status.get('out-data', ''))
            except (ValueError, TypeError):
                raise AcceptanceFailure('cloud_init_unparseable') from None
            check(isinstance(cloud, dict), 'cloud_init_unparseable')
            if cloud.get('status') in {'running', 'not started'}:
                self.pause()
                continue
            check(cloud.get('status') == 'done' and cloud.get('extended_status') == 'done'
                  and cloud.get('errors') == [] and cloud.get('recoverable_errors') == {}
                  and str(cloud.get('boot_status_code', '')).startswith('enabled-'), 'cloud_init_failed')
            self.mark('cloud_init', 'passed', 'verified')
            if self.temporary.get('disk_size_gib') is not None or self.temporary.get('nameservers') is not None:
                self.verify_general_guest(cloud.get('general_template'))
            break
        else:
            raise AcceptanceFailure('guest_timeout')
        self.stage = 'injected_hostname'
        hostname = self.api('GET', self.base + '/agent/get-host-name')
        save(self.root / 'hostname.json', hostname)
        check(isinstance(hostname, dict) and isinstance(hostname.get('result'), dict)
              and hostname['result'].get('host-name') == self.request['cloud_init']['hostname'], 'hostname_mismatch')
        self.mark('injected_hostname', 'passed', 'verified')

    def verify_general_guest(self, facts: Any) -> None:
        self.stage = 'disk_boot'
        check(isinstance(facts, dict), 'guest_observation_missing')
        if self.temporary.get('disk_size_gib') is not None:
            size = self.temporary['disk_size_gib'] * 1024 ** 3
            check(facts.get('root_disk_bytes') == size
                  and type(facts.get('root_partition_bytes')) is int and facts['root_partition_bytes'] >= size - 1024 ** 3
                  and type(facts.get('root_filesystem_bytes')) is int and facts['root_filesystem_bytes'] >= size * 95 // 100,
                  'guest_disk_growth_mismatch')
        ip = dict(part.split('=', 1) for part in self.temporary['ip_config'].split(','))
        check(ip.get('ip') in {'dhcp', None} or ip['ip'] in facts.get('addresses', []), 'guest_network_mismatch')
        check('gw' not in ip or ip['gw'] in facts.get('default_gateways', []), 'guest_network_mismatch')
        check(set(self.temporary.get('nameservers') or []) <= set(facts.get('nameservers', [])), 'guest_dns_mismatch')
        check(facts.get('machine_id_initialized') is True and isinstance(facts.get('instance_id'), str)
              and facts['instance_id'] and not facts['instance_id'].startswith('iaas-build'), 'guest_identity_mismatch')
        self.journal['general_template_guest'] = facts
        self.persist()

    def mark(self, name: str, status: str, reason: str) -> None:
        for item in self.result['checks']:
            if item['id'] == name:
                evidence = {'cloud_init': 'cloud-init-status.json', 'injected_hostname': 'hostname.json'}.get(name, 'journal.json')
                item.update(status=status, reason_code=reason,
                            evidence_ref=evidence if (self.root / evidence).is_file() else None)

    def cleanup(self) -> None:
        self.phase = 'cleanup'
        self.budget.limit('cleanup', self.request['timeouts']['cleanup_seconds'])
        self.deadline = min(self.budget.bounds['cleanup'], self.budget.local['cleanup'])
        self.remaining()
        cleanup = self.result['cleanup']
        sent_tasks = [item for item in self.journal['tasks'] if item['status'] not in {'not_sent', 'rejected'}]
        if self.journal['mutation_active'] or (self.owned is None and sent_tasks):
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
        retry_until = time.monotonic() + min(30, self.remaining())
        while True:
            try:
                rows = self.api('GET', f"/api2/json/nodes/{quote(self.temporary['node'], safe='')}/storage/{quote(self.temporary['storage'], safe='')}/content")
                break
            except RequestOutcomeUnknown as exc:
                if exc.http_status not in {500, 502, 503, 504} or time.monotonic() >= retry_until:
                    raise
                prior = self.journal.get('cleanup_inventory_retries', {}).get('count', 0)
                self.journal['cleanup_inventory_retries'] = {'count': prior + 1, 'last_http_status': exc.http_status}
                self.persist()
                time.sleep(min(1, self.remaining(), max(0, retry_until - time.monotonic())))
        check(isinstance(rows, list) and all(isinstance(row, dict) and 'volid' in row for row in rows),
              'volume_inventory_incomplete')
        self.remaining_volumes = sorted(set(self.owned['volumes']).intersection(row['volid'] for row in rows))
        check(not self.remaining_volumes, 'volumes_still_present')
        cleanup['volumes'] = {'status': 'passed', 'reason_code': 'deleted', 'evidence_ref': 'journal.json'}

    def execute(self) -> dict[str, Any]:
        self.result = {'kind': 'pve-template-acceptance-result', 'schema_version': 3,
            'cluster_scope': self.request['cluster_scope'], 'pool': self.temporary['pool'],
            'vmid_policy': self.request['vmid_policy'],
            'preview_digest': self.journal['preview_digest'], 'capacity': None,
            'deadlines': self.request['deadlines'], 'deadline_outcome': self.budget.outcome,
            'facility_writes': self.journal['facility_writes'],
            'execution_id': self.journal['execution_id'], 'request_digest': self.journal['request_digest'],
            'runtime': self.journal['runtime'],
            'template': {key: self.record[key] for key in ('record_id', 'execution_id', 'artifact_digest', 'node', 'vmid', 'smbios_uuid')},
            'temporary_resources': [],
            'checks': [{'id': name, 'status': 'not_attempted', 'reason_code': 'not_attempted', 'evidence_ref': None} for name in CHECKS],
            'failure_stage': None, 'cleanup': {name: {'status': 'not_required', 'reason_code': 'not_created', 'evidence_ref': None} for name in ('vm', 'volumes', 'snippets')},
            'residuals': {'inventory_complete': True, 'items': []}, 'overall': 'unknown', 'collection': {'status': 'complete', 'reason_code': 'collected'}}
        try:
            self.budget.admit()
            observed = admit_acceptance(ReadBudgetClient(self.client, self.budget), self.request, helpers=self.snippets)
            self.result['capacity'] = observed['capacity']
            self.source_before = observed['source_snapshot']
            self.journal.update(source_before=self.source_before, admission_observed=observed)
            self.persist()
            self.mutation('clone', 'POST', self.source + '/clone',
                          fields={'newid': self.temporary['vmid'], 'full': 1, 'target': self.temporary['node'],
                                  'storage': self.temporary['storage'], 'pool': self.temporary['pool'],
                                  'name': self.request['cloud_init']['hostname']}, node=self.record['node'])
            config = self.claim()
            self.mark('full_clone', 'passed', 'verified')
            self.stage = 'disk_boot'
            self.configure(config)
            self.mark('disk_boot', 'passed', 'verified')
            self.identity(self.api('GET', self.base + '/config'))
            self.mutation('start', 'POST', self.base + '/status/start')
            self.guest()
        except Exception as exc:
            if isinstance(exc, AdmissionError):
                self.journal['admission_diagnostic'] = exc.diagnostic
                self.result['capacity'] = exc.diagnostic.get('capacity', self.result['capacity'])
                self.persist()
            admission_unknown = isinstance(exc, AdmissionError) and (
                exc.reason_code.endswith('query_failed') or exc.reason_code.endswith('evidence_insufficient'))
            unknown = admission_unknown or not isinstance(exc, (AcceptanceFailure, AdmissionError, DeadlineExpired, LocalTimeout)) or self.journal['mutation_active']
            self.mark(self.stage, 'unknown' if unknown else 'failed',
                      str(exc) if isinstance(exc, (AcceptanceFailure, AdmissionError, UnknownOutcome, DeadlineExpired, LocalTimeout)) else 'observation_unknown')
            self.result['failure_stage'] = self.stage
        finally:
            if self.budget.outcome['status'] == 'rejected':
                self.journal['deadline_outcome'] = dict(self.budget.outcome)
                self.result['deadline_outcome'] = self.budget.outcome
                self.result['facility_writes'] = self.journal['facility_writes']
                self.result['overall'] = 'failed'
                return validate_acceptance_result(self.result)
            try:
                self.cleanup()
            except Exception as exc:
                status = 'failed' if isinstance(exc, (AcceptanceFailure, DeadlineExpired, LocalTimeout)) and not self.journal['mutation_active'] else 'unknown'
                for name in ('vm', 'volumes'):
                    if self.result['cleanup'][name]['status'] != 'passed':
                        self.result['cleanup'][name] = {'status': status, 'reason_code': 'cleanup_incomplete', 'evidence_ref': 'journal.json'}
                resources = self.resources()
                self.result['residuals'] = {'inventory_complete': self.owned is not None,
                    'items': [{**resource, 'existence': 'present' if self.remaining_volumes is not None else 'unknown', 'reason_code': 'cleanup_incomplete'}
                              for resource in resources if resource['kind'] != 'snippet'
                              if self.result['cleanup']['vm' if resource['kind'] == 'vm' else 'volumes']['status'] != 'passed'
                              and (self.remaining_volumes is None or resource['identity'] in self.remaining_volumes)]}
            try:
                self.cleanup_snippets()
            except Exception:
                self.result['cleanup']['snippets'] = {'status': 'unknown', 'reason_code': 'cleanup_incomplete', 'evidence_ref': 'journal.json'}
                self.result['residuals']['items'].extend(
                    {**resource, 'existence': 'unknown', 'reason_code': 'cleanup_incomplete'}
                    for resource in self.resources() if resource['kind'] == 'snippet')
            try:
                self.source_check(initial=False)
                self.mark('source_unchanged', 'passed', 'verified')
            except Exception as exc:
                reason = str(exc) if isinstance(exc, (AcceptanceFailure, UnknownOutcome, DeadlineExpired, LocalTimeout)) else 'source_query_failed'
                self.mark('source_unchanged', 'failed' if isinstance(exc, AcceptanceFailure) else 'unknown', reason)
        self.result['temporary_resources'] = self.resources()
        self.result['deadline_outcome'] = self.budget.outcome
        self.journal['deadline_outcome'] = dict(self.budget.outcome)
        self.result['facility_writes'] = self.journal['facility_writes']
        statuses = [item['status'] for item in self.result['checks']] + [item['status'] for item in self.result['cleanup'].values()]
        self.result['overall'] = ('unknown' if 'unknown' in statuses or any(x['existence'] == 'unknown' for x in self.result['residuals']['items']) or not self.result['residuals']['inventory_complete'] else 'passed'
                                  if all(item in {'passed', 'not_required'} for item in statuses) else 'failed')
        return validate_acceptance_result(self.result)

    def resources(self) -> list[dict[str, Any]]:
        if not any(item['status'] != 'not_sent' for item in self.journal['tasks']):
            return []
        common = {'node': self.temporary['node'], 'created_by': self.journal['execution_id'],
                  'ownership': 'owned' if self.owned else 'unknown'}
        return [{**common, 'kind': 'vm', 'identity': str(self.temporary['vmid'])}] + [
            {**common, 'kind': 'volume', 'identity': volume} for volume in (self.owned or {}).get('volumes', [])] + [
            {**common, 'kind': 'snippet', 'identity': s['file_id'],
             'ownership': 'owned' if s['uploaded'] else 'unknown'} for s in self.journal.get('snippets', [])]


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
        if request is None:
            raise ValidationError('acceptance_request is required')
        admission_path = selected.files.get('execution_admission')
        admission = load_strict_json(Path(admission_path)) if admission_path else selected.options.get('admission')
        budget = DeadlineBudget(request['deadlines'])
        preview_path = selected.files.get('acceptance_preview')
        require(preview_path is not None, 'acceptance_preview required')
        preview = load_strict_json(Path(preview_path))
        journal = begin(root, 'accept', request, admission, execution_id, image_digest, preview=preview)
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
        snippets = acceptance_snippets.Snippets(selected, execution, request['timeouts']['work_seconds'],
                                               request['cloud_init']['ssh'], budget=budget, phase='work')
        result = Acceptance(client, request, journal, root, snippets, budget).execute()
        journal.update(status='finished', result_digest=canonical_digest(result))
        save(root / 'journal.json', journal)
    save(root / 'result.json', result)
    save(execution.outputs.path('diagnostics') / 'result.json', result)
    if result['overall'] != 'passed':
        raise OperationFailed('template acceptance did not pass; inspect protected result')
    execution.finish({'component': 'pve-template', 'operation': operation, 'execution_id': result['execution_id'],
                      'overall': result['overall'], 'request_digest': result['request_digest']})
