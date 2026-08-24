"""Derive the live-resource expectations from the validated inventory model.

Used resources are blocking requirements; declared-but-unused placeholders stay
as warnings so the current inventory can carry reserved room for expansion.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class DerivedResources:
    """Expected live PVE state split into required and optional buckets."""
    required_nodes: set[str]
    optional_nodes: set[str]
    bridges_by_node: dict[str, set[str]]
    storage_by_node: dict[str, list[dict[str, Any]]]
    templates: list[dict[str, Any]]
    vmid_expectations: list[dict[str, Any]]
    mappings_by_node: dict[str, set[str]]
    optional_mapping_nodes: dict[str, set[str]]


def _expected_vm_tags(vm: dict[str, Any]) -> list[str]:
    """Preserve the ownership tag set used by OpenTofu-managed VMs."""
    networks = [nic["network"]["name"] for nic in vm.get("nics") or []]
    tags = ["managed-by-opentofu", vm["lifecycle_class"], *networks, *vm["tags"]]
    seen: set[str] = set()
    ordered: list[str] = []
    for tag in tags:
        if tag not in seen:
            seen.add(tag)
            ordered.append(tag)
    return ordered


def derive_expected_resources(model: dict[str, Any]) -> DerivedResources:
    """Translate validated model data into read-only preflight expectations."""
    cluster = model["cluster"]
    vms = model["vms"]

    required_nodes = {vm["node"] for vm in vms} | {vm["template"]["node"] for vm in vms}
    declared_nodes = set(cluster["nodes"])
    optional_nodes = declared_nodes - required_nodes

    bridges_by_node: dict[str, set[str]] = {}
    storage_by_node: dict[str, list[dict[str, Any]]] = {}
    mappings_by_node: dict[str, set[str]] = {}
    optional_mapping_nodes: dict[str, set[str]] = {}

    def add_storage(node: str, role_name: str) -> None:
        role = cluster["storage_roles"][role_name]
        storage_by_node.setdefault(node, [])
        if not any(item["role"] == role_name for item in storage_by_node[node]):
            storage_by_node[node].append(
                {
                    "role": role_name,
                    "datastore": role["datastore"],
                    "content": list(role.get("content", [])),
                    "purpose": role.get("purpose"),
                }
            )

    for vm in vms:
        node = vm["node"]
        for nic in vm.get("nics") or []:
            bridges_by_node.setdefault(node, set()).add(nic["network"]["bridge"])
        add_storage(node, vm["storage"]["disk_role"])
        add_storage(node, cluster["automation"]["cloud_init"]["snippet_storage_role"])
        add_storage(vm["template"]["node"], vm["template"]["storage_role"])
        add_storage(vm["template"]["node"], cluster["automation"]["template_build"]["import_storage_role"])
        add_storage(vm["template"]["node"], cluster["automation"]["template_build"]["disk_storage_role"])

        for mapping in vm.get("passthrough") or []:
            mappings_by_node.setdefault(node, set()).add(mapping["mapping"])

    for mapping_name, mapping in cluster["pci_mappings"].items():
        declared_mapping_nodes = set(mapping.get("nodes", {}))
        used_nodes = {node for node, names in mappings_by_node.items() if mapping_name in names}
        optional_mapping_nodes[mapping_name] = declared_mapping_nodes - used_nodes

    templates_by_vmid: dict[int, dict[str, Any]] = {}
    for vm in vms:
        template = vm["template"]
        templates_by_vmid.setdefault(
            template["vmid"],
            {
                "key": template["name"],
                "vmid": template["vmid"],
                "name": template["vm_name"],
                "node": template["node"],
            },
        )

    templates = list(templates_by_vmid.values())
    vmid_expectations = [
        {
            "vmid": vm["vmid"],
            "name": vm["name"],
            "node": vm["node"],
            "tags": _expected_vm_tags(vm),
            "cluster_marker": f"Managed by OpenTofu for {cluster['name']}",
        }
        for vm in vms
    ]

    return DerivedResources(
        required_nodes=required_nodes,
        optional_nodes=optional_nodes,
        bridges_by_node=bridges_by_node,
        storage_by_node=storage_by_node,
        templates=templates,
        vmid_expectations=vmid_expectations,
        mappings_by_node=mappings_by_node,
        optional_mapping_nodes=optional_mapping_nodes,
    )
