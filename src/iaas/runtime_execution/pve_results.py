"""Private native expectations and read-only PVE verification.

Public summaries contain counts/status only. Resource addresses, state and API
configuration remain in the protected task output, never in CLI diagnostics.
"""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
import re
import time
from typing import Any

from iaas.common.errors import require
from iaas.pve_inventory.pve_api import (
    ReadOnlyPveApi, PveApiRuntimeConfig, PveApiTlsError, PveApiUnavailableError,
)

VM_TYPE = "proxmox_virtual_environment_vm"
HA_TYPE = "proxmox_virtual_environment_haresource"
ACTIONS = {("no-op",), ("create",), ("update",), ("delete",),
           ("delete", "create"), ("create", "delete"), ("read",)}


def observed_vmids(api: Any, vmids: set[int]) -> set[int]:
    """Read a cluster list proven complete for the requested VMIDs.

    PVE filters cluster resources by VM.Audit. Check each exact ACL path using
    the current token (including privilege separation and ACL overrides), since
    a grant on /vms alone cannot prove visibility of all its children.
    """
    for vmid in sorted(vmids):
        require(type(vmid) is int and vmid > 0, "invalid VMID for existence observation")
        path = f"/vms/{vmid}"
        permissions = api.effective_permissions(path)
        grants = permissions.get(path) if isinstance(permissions, dict) else None
        require(isinstance(grants, dict) and type(grants.get("VM.Audit")) in {int, bool}
                and grants["VM.Audit"] in (0, 1),
                "VM existence observation requires effective VM.Audit on each selected VMID")
    if not vmids:
        return set()
    inventory = api.cluster_vm_resources()
    require(isinstance(inventory, list), "PVE resource observation is incomplete")
    occupied: set[int] = set()
    for row in inventory:
        require(isinstance(row, dict) and type(row.get("vmid")) is int and row["vmid"] > 0
                and row.get("type") in {"qemu", "lxc"}
                and isinstance(row.get("node"), str) and bool(row["node"]),
                "PVE resource observation is incomplete")
        require(row["vmid"] not in occupied, "PVE resource observation has duplicate VMIDs")
        occupied.add(row["vmid"])
    return occupied & vmids


def _unknown(value: Any) -> bool:
    if isinstance(value, dict):
        return any(_unknown(v) for v in value.values())
    if isinstance(value, list):
        return any(_unknown(v) for v in value)
    return value is True


def api_client(target: dict, environ: dict) -> ReadOnlyPveApi:
    return ReadOnlyPveApi(PveApiRuntimeConfig(
        endpoint=target["api_endpoint"], insecure=target["insecure"],
        api_username=environ["TF_VAR_pve_api_username"],
        api_token_id=environ["TF_VAR_pve_api_token_id"],
        api_token_secret=environ["TF_VAR_pve_api_token_secret"],
        api_ca=environ.get("PVE_API_CA") or None))


def machine_review(native: dict) -> tuple[dict, list[dict], list[dict]]:
    """Derive actions and clone dependencies from native JSON, not declarations."""
    counts: Counter = Counter()
    changes, dependencies = [], []
    for item in native.get("resource_changes", []):
        if item.get("mode", "managed") != "managed":
            continue
        action = tuple(item["change"]["actions"])
        require(action in ACTIONS, "unsupported native plan action")
        require(item.get("type") in {VM_TYPE, HA_TYPE}, "unsupported managed PVE resource")
        counts["replace" if len(action) == 2 else action[0]] += 1
        if action in {("no-op",), ("read",)}:
            continue
        changes.append(deepcopy(item))
        if item["type"] == VM_TYPE and "create" in action:
            change = item["change"]
            unknown = change.get("after_unknown", {})
            require(not _unknown(unknown.get("clone")), "unknown clone dependency")
            clone = (change.get("after") or {}).get("clone", [])
            require(isinstance(clone, list), "unknown clone dependency")
            for source in clone:
                require(isinstance(source.get("vm_id"), int) and source["vm_id"] > 0
                        and isinstance(source.get("node_name"), str) and source["node_name"],
                        "unknown clone dependency")
                dependency = {"node": source["node_name"], "vmid": source["vm_id"]}
                if dependency not in dependencies:
                    dependencies.append(dependency)
    return {"schema_version": 1, "actions": dict(counts), "changed_resources": len(changes),
            "clone_dependencies": len(dependencies)}, changes, dependencies


def state_instances(state: dict) -> dict[str, list[dict]]:
    """Read raw native state without root outputs or a new provider refresh."""
    result: dict[str, list[dict]] = {}
    for resource in state.get("resources", []):
        if resource.get("mode", "managed") != "managed":
            continue
        prefix = resource.get("module", "")
        prefix = prefix + "." if prefix else ""
        base = prefix + resource["type"] + "." + resource["name"]
        for instance in resource.get("instances", []):
            import json
            address = base
            if "index_key" in instance:
                address += "[" + json.dumps(instance["index_key"], ensure_ascii=False) + "]"
            result.setdefault(address, []).append(instance)
    return result


def _resolve(planned: Any, unknown: Any, actual: Any) -> Any:
    # Only unknown values come from the original post-apply snapshot. Known
    # plan expectations must survive provider drift and later observations.
    if unknown is True:
        return deepcopy(actual)
    if isinstance(planned, dict):
        unknown = unknown if isinstance(unknown, dict) else {}
        actual = actual if isinstance(actual, dict) else {}
        return {key: _resolve(planned.get(key), unknown.get(key), actual.get(key))
                for key in set(planned) | set(unknown)}
    if isinstance(planned, list):
        return [_resolve(value, unknown[i] if isinstance(unknown, list) and i < len(unknown) else None,
                         actual[i] if isinstance(actual, list) and i < len(actual) else None)
                for i, value in enumerate(planned)]
    return deepcopy(planned)


def expectations(changes: list[dict], snapshot: dict | None) -> list[dict]:
    instances = state_instances(snapshot) if snapshot is not None else {}
    expected = []
    for item in changes:
        change, address = item["change"], item["address"]
        current = instances.get(address, [])
        live = [i for i in current if not i.get("deposed")]
        actual = live[0].get("attributes", {}) if len(live) == 1 else {}
        before = change.get("before") or {}
        action = change["actions"]
        after = _resolve(change.get("after") or {}, change.get("after_unknown", {}), actual)
        def identity(value: dict) -> dict:
            return {"node": value.get("node_name"), "vmid": value.get("vm_id")}
        if item["type"] == HA_TYPE:
            expected.append({"kind": "ha", "action": action, "values": after if "create" in action or "update" in action else before,
                             "absent": action == ["delete"], "snapshot_complete": snapshot is not None})
            continue
        if action == ["delete"]:
            expected.append({"kind": "vm", **identity(before), "absent": True,
                             "state_absent": not current, "snapshot_complete": snapshot is not None})
            continue
        # An address match alone does not bind the snapshot to this VM. Only
        # borrow computed values/native identity from the planned object.
        snapshot_identity = "unknown"
        if isinstance(actual.get("node_name"), str) and actual["node_name"] \
                and type(actual.get("vm_id")) is int and actual["vm_id"] > 0:
            snapshot_identity = "passed" if identity(actual) == identity(after) else "failed"
        expected.append({"kind": "vm", **identity(after), "absent": False, "values": after,
                         "native_identity": actual.get("smbios", []),
                         "snapshot_complete": snapshot is not None and len(live) == 1,
                         "snapshot_identity": snapshot_identity,
                         "deposed": any(i.get("deposed") for i in current),
                         "replacement": "delete" in action,
                         "before_identity": before.get("smbios", [])})
        if "delete" in action and identity(before) != identity(after):
            expected.append({"kind": "vm", **identity(before), "absent": True,
                             "state_absent": not any(i.get("deposed") for i in current),
                             "snapshot_complete": snapshot is not None})
    return expected


def _parts(value: Any) -> dict[str, str]:
    if not isinstance(value, str):
        return {}
    return {key: val for token in value.split(",") if "=" in token for key, val in [token.split("=", 1)]}


def template_identity(config: dict) -> dict:
    disks = {key: str(value).split(",", 1)[0] for key, value in config.items()
             if re.fullmatch(r"(?:scsi|virtio|sata|ide)\d+", key) and "media=cdrom" not in str(value)}
    uuid = _parts(config.get("smbios1")).get("uuid")
    require(bool(uuid) and bool(disks), "template native identity is missing")
    return {"smbios_uuid": uuid, "disks": disks}


def _size_gib(value: str | None) -> float | None:
    match = re.fullmatch(r"([0-9.]+)([KMGT]?)", value or "")
    if not match:
        return None
    return float(match[1]) * {"": 1 / 1024**3, "K": 1 / 1024**2, "M": 1 / 1024, "G": 1, "T": 1024}[match[2]]


def _vm_fields(expected: dict, config: dict, status: dict) -> dict[str, str]:
    checks: dict[str, str] = {}

    def compare(name: str, want: Any, got: Any) -> None:
        checks[name] = "unknown" if want is None or got is None else "passed" if want == got else "failed"

    values = expected["values"]
    cpu, memory = values.get("cpu") or [{}], values.get("memory") or [{}]
    compare("cores", cpu[0].get("cores"), config.get("cores"))
    if cpu[0].get("type") is not None:
        compare("cpu_type", cpu[0]["type"], str(config.get("cpu", "")).split(",")[0] or None)
    if cpu[0].get("sockets") is not None:
        compare("sockets", cpu[0]["sockets"], config.get("sockets", 1))
    compare("memory", memory[0].get("dedicated"), int(config["memory"]) if str(config.get("memory", "")).isdigit() else None)
    compare("power", "running" if values.get("started") is True else "stopped" if values.get("started") is False else None, status.get("status"))
    if values.get("on_boot") is not None:
        compare("on_boot", values["on_boot"], str(config.get("onboot", 0)) == "1")
    for field, api_field in (("bios", "bios"), ("machine", "machine"), ("scsi_hardware", "scsihw")):
        if values.get(field) is not None:
            actual = config.get(api_field)
            # PVE omits its optional bios field for the native seabios default.
            # Preserve strict comparison for explicit values and other fields.
            if field == "bios" and actual is None:
                actual = "seabios"
            compare(field, values[field], actual)
    for i, disk in enumerate(values.get("disk") or []):
        raw = config.get(disk.get("interface"))
        volume = str(raw).split(",", 1)[0] if raw else None
        compare(f"disk.{i}.storage", disk.get("datastore_id"), volume.split(":", 1)[0] if volume else None)
        compare(f"disk.{i}.size", disk.get("size"), _size_gib(_parts(raw).get("size")))
        if disk.get("file_id"):
            compare(f"disk.{i}.volume", disk["file_id"], volume)
    if not values.get("disk"):
        checks["disks"] = "unknown"
    expected_disks = {d.get("interface") for d in values.get("disk") or []}
    efi_disks = values.get("efi_disk") or []
    if efi_disks:
        expected_disks.add("efidisk0")
        raw = config.get("efidisk0")
        volume = str(raw).split(",", 1)[0] if raw else None
        compare("efi_disk.storage", efi_disks[0].get("datastore_id"),
                volume.split(":", 1)[0] if volume else None)
        compare("efi_disk.type", efi_disks[0].get("type"), _parts(raw).get("efitype"))
    actual_disks = {k for k, v in config.items() if re.fullmatch(r"(?:scsi|sata|virtio|ide|efidisk)\d+", k)
                    and "media=cdrom" not in str(v) and "cloudinit" not in str(v)}
    compare("disk_attachments", expected_disks, actual_disks)
    if any(re.fullmatch(r"unused\d+", k) for k in config):
        checks["unused_disks"] = "failed"
    for i, nic in enumerate(values.get("network_device") or []):
        raw = _parts(config.get(f"net{i}"))
        compare(f"nic.{i}.bridge", nic.get("bridge"), raw.get("bridge"))
        model = nic.get("model") or "virtio"
        mac = nic.get("mac_address")
        compare(f"nic.{i}.mac", mac.upper() if isinstance(mac, str) else None,
                raw[model].upper() if raw.get(model) else None)
    compare("network_attachments", {f"net{i}" for i, _ in enumerate(values.get("network_device") or [])},
            {k for k in config if re.fullmatch(r"net\d+", k)})
    for init in values.get("initialization") or []:
        custom = _parts(config.get("cicustom"))
        for field, key in (("user_data_file_id", "user"), ("network_data_file_id", "network")):
            if field in init:
                compare(f"cloudinit.{key}", init[field], custom.get(key))
    for pci in values.get("hostpci") or []:
        raw = _parts(config.get(pci.get("device")))
        compare("pci." + str(pci.get("device")), pci.get("mapping"), raw.get("mapping"))
        for field in ("pcie", "rombar", "xvga"):
            if pci.get(field) is not None:
                compare("pci." + str(pci.get("device")) + "." + field,
                        str(int(pci[field])), raw.get(field, {"pcie": "0", "rombar": "1", "xvga": "0"}[field]))
    native = expected.get("native_identity") or []
    uuid = native[0].get("uuid") if native else None
    if uuid:
        compare("native_identity", uuid, _parts(config.get("smbios1")).get("uuid"))
    if expected.get("replacement"):
        before = expected.get("before_identity") or []
        prior_uuid = before[0].get("uuid") if before else None
        checks["replacement_identity"] = "unknown" if not uuid else "failed" if uuid == prior_uuid else "passed"
    return checks


class VerificationBudget:
    """One independent query window; an enclosing execution bound only tightens it."""
    def __init__(self, timeout: float = 120, *, enclosing: Any = None, phase: str = "work"):
        from iaas.observation import ObservationBudget
        cutoff = (getattr(enclosing, 'absolute', {}).get(phase) if enclosing is not None else None)
        if cutoff is None and enclosing is not None:
            cutoff = getattr(enclosing, 'cutoff', None)
        source = 'internal-default' if timeout == 120 else 'applicable-timeout'
        self.budget = ObservationBudget(timeout, cutoff=cutoff, source=source + '+execution-cutoff' if cutoff is not None else source)
        self.enclosing, self.phase = enclosing, phase
        self.cutoff = self.budget.cutoff
        self.window = self.budget.facts()
        if enclosing is not None:
            self.window['enclosing_cutoff'] = getattr(enclosing, 'deadlines', {}).get(f'{phase}_deadline_at')

    def remaining(self, phase: str) -> float:
        remaining = self.budget.remaining('work')
        return min(remaining, self.enclosing.remaining(self.phase)) if self.enclosing else remaining


def verify_configuration(expected: list[dict], api: Any, *, budget: Any = None,
                         timeout: float = 120, interval: float = 1, window: Any = None) -> dict:
    from iaas.observation import Decision, EvidenceSink, observe, utc_text
    window = window or VerificationBudget(timeout, enclosing=budget)
    observations = EvidenceSink()
    if isinstance(api, ReadOnlyPveApi):
        api.observation_budget = window
    def query(method, *args):
        window.remaining('work')
        value = getattr(api, method)(*args)
        window.remaining('work')
        return value

    items = []
    for wanted in expected:
        checks: dict[str, str] = {}
        def original_check(name, status):
            observations({'phase': 'work', 'check': name, 'association': {
                **{key: wanted[key] for key in ('node', 'vmid') if key in wanted},
                **({'resource_id': wanted.get('values', {}).get('resource_id')} if wanted['kind'] == 'ha' else {})},
                'attempt': 0, 'observed_at': utc_text(time.time()), 'status': status,
                'reason': name + '_' + status, 'evidence': {'complete': wanted.get('snapshot_complete')}})
        if not wanted.get("snapshot_complete"):
            original_check('original_snapshot', 'unknown')
            items.append({"status": "unknown", "checks": {"original_snapshot": "unknown"}})
            continue
        if wanted["kind"] == "vm" and not wanted["absent"] \
                and wanted.get("snapshot_identity") != "passed":
            status = "failed" if wanted.get("snapshot_identity") == "failed" else "unknown"
            original_check('snapshot_identity', status)
            items.append({"status": status, "checks": {"snapshot_identity": status}})
            continue
        comparison = {}
        def probe(remaining):
            checks = {}
            comparison.clear()
            values = wanted.get('values', {})
            native = wanted.get('native_identity') or [{}]
            comparison['expected'] = {'node': wanted.get('node'), 'vmid': wanted.get('vmid'),
                                      'uuid': native[0].get('uuid'), 'pool': values.get('pool_id'),
                                      'cores': (values.get('cpu') or [{}])[0].get('cores'),
                                      'memory': (values.get('memory') or [{}])[0].get('dedicated'),
                                      'power': 'running' if values.get('started') is True else 'stopped' if values.get('started') is False else None,
                                      'volumes': [{'slot': d.get('interface'), 'storage': d.get('datastore_id'),
                                                   'volid': d.get('file_id'), 'size': d.get('size')} for d in values.get('disk') or []]
                                                 + [{'slot': 'efidisk0', 'storage': d.get('datastore_id'),
                                                     'type': d.get('type')} for d in values.get('efi_disk') or []],
                                      'exists': not wanted.get('absent')}
            comparison['actual'] = {}
            if wanted["kind"] == "ha":
                values = wanted["values"]
                resource_id = values.get("resource_id")
                record = next((r for r in query('ha_status') if r.get("sid") == resource_id), None)
                comparison['actual'] = {'status': record.get('state') if record else None, 'exists': record is not None}
                if not resource_id:
                    checks["ha"] = "unknown"
                elif wanted["absent"]:
                    checks["existence"] = "pending" if record else "passed"
                else:
                    checks["ha"] = "passed" if record and record.get("state") == values.get("state") else "pending" if record is None else "failed"
            elif not isinstance(wanted.get("vmid"), int) or not wanted.get("node"):
                checks["identity"] = "unknown"
            elif wanted["absent"]:
                query('node_status', wanted['node'])
                # This helper makes several reads, all governed by the facade's budget.
                occupied = observed_vmids(api, {wanted["vmid"]})
                window.remaining('work')
                checks["existence"] = "pending" if occupied else "passed"
                comparison['actual'] = {'vmid': wanted['vmid'], 'exists': bool(occupied)}
                if occupied:
                    row = next((row for row in query('cluster_vm_resources') if row.get('vmid') == wanted['vmid']), None)
                    if row:
                        comparison['actual'].update(node=row.get('node'), pool=row.get('pool'))
                    if row and (row.get('node') != wanted['node'] or row.get('type') != 'qemu'):
                        checks['identity'] = 'failed'
            else:
                config = query('vm_config', wanted['node'], wanted['vmid'])
                state = query('vm_status', wanted['node'], wanted['vmid'])
                require(isinstance(config, dict) and isinstance(state, dict), 'invalid VM observation')
                comparison['actual'] = {'node': wanted['node'], 'vmid': wanted['vmid'], 'exists': True,
                                        'uuid': _parts(config.get('smbios1')).get('uuid'),
                                        'cores': config.get('cores'), 'memory': config.get('memory'),
                                        'power': state.get('status'),
                                        'volumes': [{'slot': slot, 'volid': str(value).split(',', 1)[0],
                                                     'size': _size_gib(_parts(value).get('size'))}
                                                    for slot, value in config.items() if re.fullmatch(r'(?:scsi|virtio|sata|ide|efidisk)\d+', slot)
                                                    and 'media=cdrom' not in str(value) and 'cloudinit' not in str(value)]}
                checks = _vm_fields(wanted, config, state)
                # Explicit conflicting configuration/identity is terminal. Missing
                # synchronized fields and power transition alone can converge.
                missing_expected = {'replacement_identity'}
                for name, value in [('cores', comparison['expected']['cores']), ('memory', comparison['expected']['memory']), ('power', comparison['expected']['power'])]:
                    if value is None:
                        missing_expected.add(name)
                if not native[0].get('uuid'):
                    checks['native_identity'] = 'unknown'
                    missing_expected.add('native_identity')
                if not values.get('disk'):
                    missing_expected.add('disks')
                for name, status in list(checks.items()):
                    if status == 'unknown' and name not in missing_expected:
                        checks[name] = 'pending'
                    elif name == 'power' and status == 'failed':
                        checks[name] = 'pending'
                if wanted.get('values', {}).get('pool_id'):
                    rows = query('cluster_vm_resources')
                    require(isinstance(rows, list), 'invalid placement observation')
                    row = next((r for r in rows if r.get('vmid') == wanted['vmid']), None)
                    comparison['actual']['pool'] = row.get('pool') if row else None
                    checks['placement'] = ('pending' if row is None else 'passed'
                                           if row.get('node') == wanted['node'] and row.get('pool') == wanted['values']['pool_id'] else 'failed')
            if wanted.get("deposed") or wanted.get("state_absent") is False:
                checks["state_residual"] = "failed"
            return checks

        def classify(checks):
            status = ('failed' if 'failed' in checks.values() else 'unknown'
                      if not checks or 'unknown' in checks.values() else 'pending'
                      if 'pending' in checks.values() else 'ready')
            return Decision(status, 'configuration_' + status, {**comparison, 'checks': [{'reason': key, 'status': value} for key, value in checks.items()]})

        def retry_error(exc):
            if isinstance(exc, PveApiTlsError):
                raise exc
            return Decision('pending' if isinstance(exc, PveApiUnavailableError) else 'unknown',
                            'temporary_read_unavailable' if isinstance(exc, PveApiUnavailableError) else 'query_unconfirmed',
                            {'category': type(exc).__name__})

        association = {**{k: wanted[k] for k in ('kind', 'node', 'vmid') if k in wanted},
                       **({'resource_id': wanted['values'].get('resource_id')} if wanted['kind'] == 'ha' else {})}
        try:
            decision = observe(probe, classify, budget=window, phase='work', check='saved_plan_configuration',
                               association=association,
                               sink=observations, interval=interval,
                               retry_error=retry_error)
            checks = {row['reason']: row['status'] for row in decision.evidence.get('checks', [])} or {'observation': 'unknown'}
            checks = {k: 'unknown' if v == 'pending' else v for k, v in checks.items()}
            status = 'passed' if decision.status == 'ready' else decision.status
        except PveApiTlsError as exc:
            observations({'phase': 'work', 'check': 'saved_plan_configuration', 'association': association,
                          'attempt': 0, 'observed_at': utc_text(time.time()), 'status': 'failed',
                          'reason': 'tls_trust_failed', 'evidence': {'category': 'tls_trust'},
                          'cutoff': window.window['cutoff']})
            exc.verification_report = {'status': 'failed', 'scope': 'changed_objects',
                                       'objects': [*items, {'status': 'failed', 'checks': {'tls_trust': 'failed'}}],
                                       'observation_window': window.window, 'observations': observations.rows()}
            raise
        items.append({"status": status, "checks": checks})
    status = "failed" if any(i["status"] == "failed" for i in items) else "unknown" if any(i["status"] == "unknown" for i in items) else "passed"
    return {"status": status, "scope": "changed_objects" if items else "empty", "objects": items,
            "observation_window": window.window, "observations": observations.rows()}


def stop_diagnostics(result: dict, report: dict | None = None) -> dict:
    """Safe native/query facts; current convergence cannot prove historical apply."""
    from iaas.pve_acceptance_contracts import StopDiagnostics
    report = report if report is not None else result.get('verification', {})
    observations = [*result.get('snippet_verification', {}).get('observations', []),
                    *report.get('observations', [])]
    completed = [name for name in ('native_execution', 'state_persistence', 'collection')
                 if result.get(name, {}).get('status') in {'success', 'passed'}]
    completed.extend(row['check'] for row in observations if row.get('terminal', {}).get('status') == 'ready')
    terminal = next((row.get('terminal') for row in observations
                     if row.get('terminal', {}).get('status') in {'failed', 'unknown'}), None)
    native = result.get('native_execution', result.get('original_native_execution', {})).get('status', 'unknown')
    stopping = ({'phase': terminal['phase'], 'check': terminal['check'], 'status': terminal['status'],
                 'reason_code': terminal['reason']} if terminal else None)
    if stopping is None and ('native_execution' in result or 'original_native_execution' in result) and native in {'failed', 'unknown'}:
        stopping = {'phase': 'apply', 'check': 'native_execution', 'status': native,
                    'reason_code': 'native_execution_' + native}
    if stopping is None and report.get('status') in {'failed', 'unknown'}:
        stopping = {'phase': 'verify', 'check': 'configuration', 'status': report['status'],
                    'reason_code': 'configuration_' + report['status']}
    if stopping is None and result.get('phase') == 'failed' and result.get('phases'):
        phase = result['phases'][-1]
        stopping = {'phase': phase.get('phase', 'execution'), 'check': 'native_phase', 'status': 'failed'
                    if phase.get('capture_complete') and phase.get('exit_code') else 'unknown', 'reason_code': 'native_phase_incomplete'}
    effect = result.get('effects', {}).get('facility')
    writes = ('issued' if effect == 'known' else 'none' if effect == 'none' else 'unknown')
    if 'effects' not in result:
        writes = 'unknown'  # Independent verification adds no write-authority evidence.
    existence = [row.get('terminal', {}).get('evidence', {}).get('actual', {}).get('exists')
                 for row in report.get('observations', [])]
    exists = ('present' if existence and all(value is True for value in existence) else
              'absent' if existence and all(value is False for value in existence) else 'unknown')
    inventory_complete = bool(report.get('objects')) and all(
        row.get('terminal', {}).get('evidence', {}).get('actual') for row in report.get('observations', [])) \
        and len(report.get('observations', [])) == len(report.get('objects', []))
    inventory_complete = inventory_complete or report.get('scope') == 'empty'
    ownership = 'registered-owned' if report.get('status') == 'passed' and exists == 'present' else 'candidate-unknown'
    activity = 'stopped' if native in {'success', 'failed'} or native == 'not_attempted' and effect in {'known', 'none'} else 'unknown'
    return StopDiagnostics.model_validate({
        'completed': completed, 'stopping': stopping, 'facility_writes': writes, 'activity': activity,
        'ownership': ownership, 'existence': exists, 'inventory_complete': inventory_complete,
        'tasks': [], 'observations': observations,
        'recovery': {'supported': False, 'disposition': 'not_applicable',
                     'reason_code': 'saved_plan_bounded_recovery_not_supported', 'required_evidence': []},
    }).model_dump(mode='json')
