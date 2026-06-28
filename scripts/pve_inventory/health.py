"""Explicit online PVE cluster health checks."""

from __future__ import annotations

import argparse
import os
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from scripts.common.errors import ValidationError
from scripts.common.io import load_yaml

from .inventory.model import build_model
from .paths import DEFAULT_CLUSTER, DEFAULT_VMS
from .pve_api import (
    HealthApiRuntimeConfig,
    PveReadOnlyApi,
    PveApiAuthenticationError,
    PveApiError,
    PveApiNotConfiguredError,
    PveApiUnavailableError,
    ReadOnlyPveApi,
    load_api_runtime_config,
    redact_sensitive_text,
)
from .checks.results import CheckResult, Severity, has_failures, render_report
from .validation import validate_cluster, validate_vms


@dataclass(frozen=True)
class HealthThresholds:
    cpu_warn_pct: float = 90.0
    memory_warn_pct: float = 90.0
    rootfs_warn_pct: float = 90.0
    rootfs_fail_pct: float = 98.0
    datastore_warn_pct: float = 85.0
    datastore_fail_pct: float = 95.0


@dataclass(frozen=True)
class HealthExpectations:
    required_nodes: set[str]
    optional_nodes: set[str]
    templates: dict[str, dict[str, Any]]
    declared_vms: list[dict[str, Any]]
    required_datastores_by_node: dict[str, set[str]]


THRESHOLDS = HealthThresholds()


def load_health_runtime_config(environ: dict[str, str] | None = None) -> HealthApiRuntimeConfig:
    return load_api_runtime_config(environ)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cluster", type=Path, default=DEFAULT_CLUSTER, help="Path to inventory/pve-cluster.yml")
    parser.add_argument("--vms", type=Path, default=DEFAULT_VMS, help="Path to inventory/vms.yml")
    return parser.parse_args(argv)


def derive_health_expectations(model: dict[str, Any]) -> HealthExpectations:
    cluster = model["cluster"]
    declared_vms = list(model["vms"])
    templates = dict(cluster["templates"])
    required_nodes = {vm["node"] for vm in declared_vms} | {template["node"] for template in templates.values()}
    optional_nodes = set(cluster["nodes"]) - required_nodes

    required_datastores_by_node: dict[str, set[str]] = defaultdict(set)
    cloud_init = cluster["automation"].get("cloud_init", {})
    shared_roles = {
        cloud_init.get("drive_storage_role"),
        cloud_init.get("snippet_storage_role"),
    }
    shared_datastores = {
        cluster["storage_roles"][role]["datastore"]
        for role in shared_roles
        if isinstance(role, str) and role in cluster["storage_roles"]
    }
    for vm in declared_vms:
        required_datastores_by_node[vm["node"]].add(vm["storage"]["disk_datastore_id"])
        required_datastores_by_node[vm["node"]].add(cluster["storage_roles"][vm["template"]["storage_role"]]["datastore"])
    for template in templates.values():
        required_datastores_by_node[template["node"]].add(cluster["storage_roles"][template["storage_role"]]["datastore"])
    for node in required_nodes:
        required_datastores_by_node[node].update(shared_datastores)

    return HealthExpectations(
        required_nodes=required_nodes,
        optional_nodes=optional_nodes,
        templates=templates,
        declared_vms=declared_vms,
        required_datastores_by_node={node: set(datastores) for node, datastores in required_datastores_by_node.items()},
    )


def _emit(results: list[CheckResult], severity: Severity, check_id: str, message: str) -> None:
    results.append(CheckResult(severity=severity, check_id=check_id, message=message))


def _as_list(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    if isinstance(value, dict):
        return [value]
    return []


def _normalize_percent(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        number = float(value)
        return number * 100.0 if 0.0 <= number <= 1.5 else number
    try:
        number = float(str(value))
    except ValueError:
        return None
    return number * 100.0 if 0.0 <= number <= 1.5 else number


def _nested_percent(record: dict[str, Any], field: str) -> float | None:
    value = record.get(field)
    if isinstance(value, dict):
        used = _normalize_percent(value.get("used"))
        total = _normalize_percent(value.get("total"))
        if used is not None and total:
            if total > 1.5:
                return (used / total) * 100.0
        return None
    return _normalize_percent(value)


def _lookup_field(record: dict[str, Any], *names: str) -> Any:
    for name in names:
        if name in record:
            return record[name]
    return None


def _ceph_health_status(data: Any) -> str:
    if not isinstance(data, dict):
        return ""
    health = data.get("health")
    if isinstance(health, dict):
        value = health.get("status") or health.get("state")
        return str(value or "").upper()
    if health is not None:
        return str(health).upper()
    return str(data.get("status") or "").upper()


def _safe_message(api: PveReadOnlyApi, message: str) -> str:
    redactor = getattr(api, "redact_operator_text", None)
    if callable(redactor):
        return redactor(message)  # type: ignore[misc]
    return redact_sensitive_text(message, [])


def _cluster_quorate(status: Any) -> bool | None:
    for item in _as_list(status):
        if "quorate" in item:
            return bool(item["quorate"])
    if isinstance(status, dict) and "quorate" in status:
        return bool(status["quorate"])
    return None


def _node_status_name(record: dict[str, Any]) -> str:
    online = record.get("online")
    if isinstance(online, bool):
        return "online" if online else "offline"
    return str(record.get("status") or online or "unknown")


def _node_cpu_percent(record: dict[str, Any]) -> float | None:
    cpu = _normalize_percent(record.get("cpu"))
    if cpu is None:
        return None
    cpuinfo = record.get("cpuinfo")
    if isinstance(cpuinfo, dict):
        cores = cpuinfo.get("cpus")
        if isinstance(cores, (int, float)) and cores > 0:
            if cpu <= 1.5:
                return cpu * 100.0
            return (cpu / float(cores)) * 100.0
    return cpu * 100.0 if cpu <= 1.5 else cpu


def _storage_usage_percent(record: dict[str, Any]) -> float | None:
    for key in ("usage", "used_percent", "use"):
        value = _normalize_percent(record.get(key))
        if value is not None:
            return value
    used = _normalize_percent(record.get("used"))
    total = _normalize_percent(record.get("total"))
    if used is not None and total:
        if total > 1.5:
            return (used / total) * 100.0
    disk = _normalize_percent(record.get("disk"))
    maxdisk = _normalize_percent(record.get("maxdisk"))
    if disk is not None and maxdisk:
        if maxdisk > 1.5:
            return (disk / maxdisk) * 100.0
    return None


def _node_memory_percent(record: dict[str, Any]) -> float | None:
    mem = _nested_percent(record, "memory")
    if mem is not None:
        return mem
    mem = _normalize_percent(record.get("mem"))
    maxmem = _normalize_percent(record.get("maxmem"))
    if mem is not None and maxmem:
        if maxmem > 1.5:
            return (mem / maxmem) * 100.0
    return None


def _node_rootfs_percent(record: dict[str, Any]) -> float | None:
    rootfs = _nested_percent(record, "rootfs")
    if rootfs is not None:
        return rootfs
    rootfs = _normalize_percent(record.get("rootfs"))
    maxrootfs = _normalize_percent(record.get("maxrootfs"))
    if rootfs is not None and maxrootfs:
        if maxrootfs > 1.5:
            return (rootfs / maxrootfs) * 100.0
    return None


def _check_api_reachability(api: PveReadOnlyApi, results: list[CheckResult]) -> Any | None:
    try:
        cluster_status = api.cluster_status()
    except PveApiAuthenticationError as exc:
        _emit(results, "FAIL", "api.reachability", _safe_message(api, str(exc)))
        return None
    except PveApiError as exc:
        _emit(results, "FAIL", "api.reachability", _safe_message(api, str(exc)))
        return None
    _emit(results, "PASS", "api.reachability", "PVE API reachable and authenticated")
    return cluster_status


def _check_quorum(cluster_status: Any, results: list[CheckResult]) -> None:
    quorate = _cluster_quorate(cluster_status)
    if quorate is None:
        _emit(results, "SKIP", "cluster.quorum", "cluster status does not expose quorum state")
    elif quorate:
        _emit(results, "PASS", "cluster.quorum", "cluster is quorate")
    else:
        _emit(results, "FAIL", "cluster.quorum", "cluster is not quorate")


def _check_nodes(api: PveReadOnlyApi, expectations: HealthExpectations, results: list[CheckResult]) -> dict[str, dict[str, Any]]:
    try:
        records = _as_list(api.nodes())
    except PveApiError as exc:
        _emit(results, "FAIL", "cluster.nodes", _safe_message(api, str(exc)))
        return {}
    node_index = {str(item.get("node")): item for item in records if item.get("node")}
    for node in sorted(expectations.required_nodes):
        record = node_index.get(node)
        if record is None:
            _emit(results, "FAIL", f"node.{node}", f"required node {node} is missing")
            continue
        status_name = _node_status_name(record)
        if status_name != "online":
            _emit(results, "FAIL", f"node.{node}", f"required node {node} is {status_name}")
        else:
            _emit(results, "PASS", f"node.{node}", f"required node {node} is online")
    for node in sorted(expectations.optional_nodes):
        record = node_index.get(node)
        if record is None:
            _emit(results, "WARN", f"node.optional.{node}", f"declared placeholder node {node} is missing")
            continue
        status_name = _node_status_name(record)
        if status_name != "online":
            _emit(results, "WARN", f"node.optional.{node}", f"declared placeholder node {node} is {status_name}")
        else:
            _emit(results, "PASS", f"node.optional.{node}", f"declared placeholder node {node} is online")
    return node_index


def _check_node_capacity(api: PveReadOnlyApi, node_index: dict[str, dict[str, Any]], results: list[CheckResult]) -> None:
    for node, record in sorted(node_index.items()):
        status = _node_status_name(record)
        if status != "online":
            continue
        try:
            status_record = api.node_status(node)
        except PveApiError as exc:
            _emit(results, "FAIL", f"node.capacity.{node}", _safe_message(api, str(exc)))
            continue
        for label, value, warn_threshold, fail_threshold in (
            ("cpu", _node_cpu_percent(status_record), THRESHOLDS.cpu_warn_pct, None),
            ("memory", _node_memory_percent(status_record), THRESHOLDS.memory_warn_pct, None),
            ("rootfs", _node_rootfs_percent(status_record), THRESHOLDS.rootfs_warn_pct, THRESHOLDS.rootfs_fail_pct),
        ):
            if value is None:
                continue
            if fail_threshold is not None and value > fail_threshold:
                _emit(results, "FAIL", f"node.capacity.{node}.{label}", f"{label} usage on {node} is {value:.1f}%")
            elif value > warn_threshold:
                _emit(results, "WARN", f"node.capacity.{node}.{label}", f"{label} usage on {node} is {value:.1f}%")
            else:
                _emit(results, "PASS", f"node.capacity.{node}.{label}", f"{label} usage on {node} is {value:.1f}%")


def _check_required_datastores(api: PveReadOnlyApi, expectations: HealthExpectations, node_index: dict[str, dict[str, Any]], results: list[CheckResult]) -> None:
    for node in sorted(expectations.required_nodes & set(node_index)):
        required = sorted(expectations.required_datastores_by_node.get(node, set()))
        if not required:
            continue
        try:
            records = _as_list(api.node_storage(node))
        except PveApiError as exc:
            _emit(results, "FAIL", f"storage.{node}", _safe_message(api, str(exc)))
            continue
        storage_index = {str(item.get("storage")): item for item in records if item.get("storage")}
        for datastore in required:
            record = storage_index.get(datastore)
            if record is None:
                _emit(results, "FAIL", f"storage.{node}.{datastore}", f"required datastore {datastore} is missing on {node}")
                continue
            active = record.get("active")
            if active is False or str(record.get("status") or "").lower() in {"inactive", "unavailable", "offline"}:
                _emit(results, "FAIL", f"storage.{node}.{datastore}", f"required datastore {datastore} is inactive on {node}")
                continue
            usage = _storage_usage_percent(record)
            if usage is not None and usage > THRESHOLDS.datastore_fail_pct:
                _emit(results, "FAIL", f"storage.{node}.{datastore}", f"required datastore {datastore} usage on {node} is {usage:.1f}%")
            elif usage is not None and usage > THRESHOLDS.datastore_warn_pct:
                _emit(results, "WARN", f"storage.{node}.{datastore}", f"required datastore {datastore} usage on {node} is {usage:.1f}%")
            else:
                _emit(results, "PASS", f"storage.{node}.{datastore}", f"required datastore {datastore} is active on {node}")


def _vm_records_by_node(api: PveReadOnlyApi, nodes: Iterable[str], results: list[CheckResult]) -> dict[str, dict[int, dict[str, Any]]]:
    vm_index: dict[str, dict[int, dict[str, Any]]] = {}
    for node in nodes:
        try:
            records = _as_list(api.vms(node))
        except PveApiError as exc:
            _emit(results, "FAIL", f"vm.index.{node}", _safe_message(api, str(exc)))
            continue
        vm_index[node] = {int(item["vmid"]): item for item in records if isinstance(item.get("vmid"), int)}
    return vm_index


def _check_templates(api: PveReadOnlyApi, expectations: HealthExpectations, vm_index: dict[str, dict[int, dict[str, Any]]], results: list[CheckResult]) -> None:
    for template_name, template in sorted(expectations.templates.items()):
        node = str(template["node"])
        records = vm_index.get(node, {})
        record = records.get(int(template["vmid"]))
        if record is None:
            _emit(results, "FAIL", f"template.{template_name}", f"referenced template {template_name} ({template['vmid']}) is missing on {node}")
            continue
        template_flag = bool(record.get("template"))
        if not template_flag:
            try:
                config = api.vm_config(node, int(template["vmid"]))
            except PveApiError as exc:
                _emit(results, "FAIL", f"template.{template_name}", _safe_message(api, str(exc)))
                continue
            template_flag = bool(config.get("template"))
        if not template_flag:
            _emit(results, "FAIL", f"template.{template_name}", f"referenced template {template_name} is not marked as a template")
        else:
            _emit(results, "PASS", f"template.{template_name}", f"referenced template {template_name} is present on {node}")


def _check_vms(api: PveReadOnlyApi, expectations: HealthExpectations, vm_index: dict[str, dict[int, dict[str, Any]]], results: list[CheckResult]) -> None:
    for vm in expectations.declared_vms:
        node = vm["node"]
        vmid = int(vm["vmid"])
        lifecycle = vm["lifecycle_class"]
        record = vm_index.get(node, {}).get(vmid)
        if record is None:
            if lifecycle == "long_lived":
                _emit(results, "WARN", f"vm.{vm['name']}", f"long-lived VM {vm['name']} ({vmid}) is missing on {node}")
            else:
                _emit(results, "SKIP", f"vm.{vm['name']}", f"ephemeral lab VM {vm['name']} ({vmid}) is missing on {node}")
            continue
        try:
            status = api.vm_status(node, vmid)
        except PveApiError as exc:
            _emit(results, "FAIL", f"vm.{vm['name']}", _safe_message(api, str(exc)))
            continue
        state = str(status.get("status") or record.get("status") or "unknown")
        if state == "running":
            _emit(results, "PASS", f"vm.{vm['name']}", f"VM {vm['name']} is running on {node}")
        elif lifecycle == "long_lived":
            _emit(results, "WARN", f"vm.{vm['name']}", f"long-lived VM {vm['name']} is {state} on {node}")
        else:
            _emit(results, "SKIP", f"vm.{vm['name']}", f"ephemeral lab VM {vm['name']} is {state} on {node}")


def _check_ha(api: PveReadOnlyApi, results: list[CheckResult]) -> None:
    try:
        records = _as_list(api.ha_status())
    except (PveApiNotConfiguredError, PveApiUnavailableError):
        _emit(results, "SKIP", "ha", "HA endpoint is unavailable or not configured")
        return
    except PveApiError as exc:
        _emit(results, "SKIP", "ha", _safe_message(api, f"HA checks unavailable: {exc}"))
        return
    if not records:
        _emit(results, "SKIP", "ha", "HA subsystem has no resources")
        return
    unhealthy: list[str] = []
    for record in records:
        state = str(_lookup_field(record, "state", "status") or "").lower()
        name = str(_lookup_field(record, "sid", "service", "name") or "ha-resource")
        if state in {"error", "fence", "fenced", "unknown", "failed", "unhealthy"}:
            unhealthy.append(name)
            _emit(results, "FAIL", f"ha.{name}", f"HA resource {name} is unhealthy ({state})")
        elif state:
            _emit(results, "PASS", f"ha.{name}", f"HA resource {name} is {state}")
    if unhealthy:
        _emit(results, "FAIL", "ha", f"HA resources unhealthy: {', '.join(unhealthy)}")
    elif records:
        _emit(results, "PASS", "ha", "HA resources are healthy")


def _check_ceph(api: PveReadOnlyApi, results: list[CheckResult]) -> None:
    try:
        data = api.ceph_status()
    except (PveApiNotConfiguredError, PveApiUnavailableError):
        _emit(results, "SKIP", "ceph", "Ceph endpoint is unavailable or not configured")
        return
    except PveApiError as exc:
        _emit(results, "SKIP", "ceph", _safe_message(api, f"Ceph checks unavailable: {exc}"))
        return
    health = _ceph_health_status(data)
    if health == "HEALTH_OK":
        _emit(results, "PASS", "ceph", "Ceph health is HEALTH_OK")
    elif health == "HEALTH_WARN":
        _emit(results, "WARN", "ceph", "Ceph health is HEALTH_WARN")
    elif health == "HEALTH_ERR":
        _emit(results, "FAIL", "ceph", "Ceph health is HEALTH_ERR")
    else:
        _emit(results, "SKIP", "ceph", "Ceph health status is unavailable")


def run_health(
    cluster_path: Path = DEFAULT_CLUSTER,
    vms_path: Path = DEFAULT_VMS,
    environ: dict[str, str] | None = None,
    api_client: PveReadOnlyApi | None = None,
) -> list[CheckResult]:
    results: list[CheckResult] = []
    runtime = load_health_runtime_config(environ) if api_client is None else None

    cluster_doc = load_yaml(cluster_path)
    cluster_state = validate_cluster(cluster_doc)
    vms_doc = load_yaml(vms_path)
    vms = validate_vms(vms_doc, cluster_state)
    model = build_model(cluster_state, vms)
    expectations = derive_health_expectations(model)

    if api_client is None:
        assert runtime is not None
        client: PveReadOnlyApi = ReadOnlyPveApi.from_runtime(runtime)
    else:
        client = api_client
    cluster_status = _check_api_reachability(client, results)
    if cluster_status is None:
        return results
    _check_quorum(cluster_status, results)
    node_index = _check_nodes(client, expectations, results)
    _check_node_capacity(client, node_index, results)
    _check_required_datastores(client, expectations, node_index, results)
    vm_index = _vm_records_by_node(client, node_index.keys(), results)
    _check_templates(client, expectations, vm_index, results)
    _check_vms(client, expectations, vm_index, results)
    _check_ha(client, results)
    _check_ceph(client, results)
    return results


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        results = run_health(cluster_path=args.cluster, vms_path=args.vms)
    except ValidationError as exc:
        print(f"FAIL model.validation: {exc}")
        return 1
    except Exception as exc:  # pragma: no cover
        print(f"FAIL health: {redact_sensitive_text(str(exc), [os.environ.get('TF_VAR_pve_api_token_secret', '')])}")
        return 1

    print(render_report(results), end="")
    return 1 if has_failures(results) else 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "CheckResult",
    "HealthExpectations",
    "HealthApiRuntimeConfig",
    "HealthThresholds",
    "THRESHOLDS",
    "derive_health_expectations",
    "load_health_runtime_config",
    "main",
    "parse_args",
    "render_report",
    "run_health",
]
