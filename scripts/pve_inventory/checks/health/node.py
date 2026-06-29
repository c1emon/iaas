"""Node and storage health checks."""

from __future__ import annotations

from typing import Any

from ...pve_api import PveApiError, PveReadOnlyApi, redact_sensitive_text
from ..results import CheckResult, Severity
from .model import HealthExpectations, THRESHOLDS


def _emit(results: list[CheckResult], severity: Severity, check_id: str, message: str) -> None:
    results.append(CheckResult(severity=severity, check_id=check_id, message=message))


def _as_list(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    if isinstance(value, dict):
        return [value]
    return []


def _normalize_percent(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
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


def _safe_message(api: PveReadOnlyApi, message: str) -> str:
    redactor = getattr(api, "redact_operator_text", None)
    if callable(redactor):
        return redactor(message)  # type: ignore[misc]
    return redact_sensitive_text(message, [])


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


def check_nodes(api: PveReadOnlyApi, expectations: HealthExpectations, results: list[CheckResult]) -> dict[str, dict[str, Any]]:
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


def check_node_capacity(api: PveReadOnlyApi, node_index: dict[str, dict[str, Any]], results: list[CheckResult]) -> None:
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


def check_required_datastores(api: PveReadOnlyApi, expectations: HealthExpectations, node_index: dict[str, dict[str, Any]], results: list[CheckResult]) -> None:
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
