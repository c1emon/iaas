"""Compatibility façade for PVE inventory validation helpers and entrypoints."""

from __future__ import annotations

from scripts.common.validation import as_list, as_mapping, require_bool, require_non_empty_string, require_positive_int, require_unknown_keys, require_url_like

from .cluster_validation import validate_automation, validate_cluster
from .vm_validation import normalize_vm_boot, normalize_vm_resources, normalize_vm_storage, parse_static_ip, validate_vms

__all__ = [
    "as_list",
    "as_mapping",
    "normalize_vm_boot",
    "normalize_vm_resources",
    "normalize_vm_storage",
    "parse_static_ip",
    "require_bool",
    "require_non_empty_string",
    "require_positive_int",
    "require_unknown_keys",
    "require_url_like",
    "validate_automation",
    "validate_cluster",
    "validate_vms",
]
