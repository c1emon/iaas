"""Internal validation helpers for offline PVE inventory data."""

from __future__ import annotations

from .cluster import validate_automation, validate_cluster
from .passthrough import normalize_vm_passthrough
from .vm import normalize_vm_boot, normalize_vm_resources, normalize_vm_storage, parse_static_ip, validate_vms

__all__ = [
    "normalize_vm_boot",
    "normalize_vm_passthrough",
    "normalize_vm_resources",
    "normalize_vm_storage",
    "parse_static_ip",
    "validate_automation",
    "validate_cluster",
    "validate_vms",
]
