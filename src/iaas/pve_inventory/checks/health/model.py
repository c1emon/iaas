"""Health expectations and thresholds."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any


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
