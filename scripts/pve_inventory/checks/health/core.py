"""Health orchestration internals."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from scripts.common.io import load_yaml

from ...inventory.model import build_model
from ...paths import DEFAULT_CLUSTER, DEFAULT_VMS
from ...pve_api import (
    PveApiAuthenticationError,
    PveApiError,
    PveReadOnlyApi,
    ReadOnlyPveApi,
    load_api_runtime_config,
    redact_sensitive_text,
)
from ...inventory.validation.cluster import validate_cluster
from ...inventory.validation.vm import validate_vms
from ..results import CheckResult, Severity
from .model import derive_health_expectations
from .infra import check_ceph, check_ha
from .node import check_node_capacity, check_nodes, check_required_datastores
from .vm import check_templates, check_vms, vm_records_by_node


def _cluster_quorate(status: Any) -> bool | None:
    if isinstance(status, list):
        for item in status:
            if isinstance(item, dict) and "quorate" in item:
                return bool(item["quorate"])
    if isinstance(status, dict) and "quorate" in status:
        return bool(status["quorate"])
    return None


def _emit(results: list[CheckResult], severity: Severity, check_id: str, message: str) -> None:
    results.append(CheckResult(severity=severity, check_id=check_id, message=message))


def _safe_message(api: PveReadOnlyApi, message: str) -> str:
    redactor = getattr(api, "redact_operator_text", None)
    if callable(redactor):
        return redactor(message)  # type: ignore[misc]
    return redact_sensitive_text(message, [])


def check_api_reachability(api: PveReadOnlyApi, results: list[CheckResult]) -> Any | None:
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


def check_quorum(cluster_status: Any, results: list[CheckResult]) -> None:
    quorate = _cluster_quorate(cluster_status)
    if quorate is None:
        _emit(results, "SKIP", "cluster.quorum", "cluster status does not expose quorum state")
    elif quorate:
        _emit(results, "PASS", "cluster.quorum", "cluster is quorate")
    else:
        _emit(results, "FAIL", "cluster.quorum", "cluster is not quorate")


def run_health_checks(
    cluster_path: Path = DEFAULT_CLUSTER,
    vms_path: Path = DEFAULT_VMS,
    environ: dict[str, str] | None = None,
    api_client: PveReadOnlyApi | None = None,
) -> list[CheckResult]:
    results: list[CheckResult] = []

    cluster_doc = load_yaml(cluster_path)
    cluster_state = validate_cluster(cluster_doc)
    vms_doc = load_yaml(vms_path)
    vms = validate_vms(vms_doc, cluster_state)
    model = build_model(cluster_state, vms)
    expectations = derive_health_expectations(model)

    if api_client is None:
        runtime = load_api_runtime_config(environ)
        client: PveReadOnlyApi = ReadOnlyPveApi.from_runtime(runtime)
    else:
        client = api_client
    cluster_status = check_api_reachability(client, results)
    if cluster_status is None:
        return results
    check_quorum(cluster_status, results)
    node_index = check_nodes(client, expectations, results)
    check_node_capacity(client, node_index, results)
    check_required_datastores(client, expectations, node_index, results)
    vm_index = vm_records_by_node(client, node_index.keys(), results)
    check_templates(client, expectations, vm_index, results)
    check_vms(client, expectations, vm_index, results)
    check_ha(client, results)
    check_ceph(client, results)
    return results
