"""VM and template health checks."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from ...pve_api import PveApiError, PveReadOnlyApi, redact_sensitive_text
from ..results import CheckResult, Severity
from .model import HealthExpectations


def _emit(results: list[CheckResult], severity: Severity, check_id: str, message: str) -> None:
    results.append(CheckResult(severity=severity, check_id=check_id, message=message))


def _as_list(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    if isinstance(value, dict):
        return [value]
    return []


def _safe_message(api: PveReadOnlyApi, message: str) -> str:
    redactor = getattr(api, "redact_operator_text", None)
    if callable(redactor):
        return redactor(message)  # type: ignore[misc]
    return redact_sensitive_text(message, [])


def vm_records_by_node(api: PveReadOnlyApi, nodes: Iterable[str], results: list[CheckResult]) -> dict[str, dict[int, dict[str, Any]]]:
    vm_index: dict[str, dict[int, dict[str, Any]]] = {}
    for node in nodes:
        try:
            records = _as_list(api.vms(node))
        except PveApiError as exc:
            _emit(results, "FAIL", f"vm.index.{node}", _safe_message(api, str(exc)))
            continue
        vm_index[node] = {int(item["vmid"]): item for item in records if isinstance(item.get("vmid"), int)}
    return vm_index


def check_templates(api: PveReadOnlyApi, expectations: HealthExpectations, vm_index: dict[str, dict[int, dict[str, Any]]], results: list[CheckResult]) -> None:
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


def check_vms(api: PveReadOnlyApi, expectations: HealthExpectations, vm_index: dict[str, dict[int, dict[str, Any]]], results: list[CheckResult]) -> None:
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
