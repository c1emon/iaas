"""Model assembly for validated PVE inventory data."""

from __future__ import annotations

from typing import Any


def build_model(cluster_state: dict[str, Any], vms: list[dict[str, Any]]) -> dict[str, Any]:
    """Combine validated cluster and VM data into the renderer model."""
    return {
        "cluster": {
            "name": cluster_state["name"],
            "default_template": cluster_state["default_template"],
            "reserved_vm_id_ranges": cluster_state["reserved_vm_id_ranges"],
            "storage_roles": cluster_state["storage_roles"],
            "automation": cluster_state["automation"],
            "networks": cluster_state["networks"],
            "nodes": cluster_state["nodes"],
            "vm_defaults": cluster_state["vm_defaults"],
            "templates": cluster_state["templates"],
            "pci_mappings": cluster_state["pci_mappings"],
        },
        "vms": vms,
    }
