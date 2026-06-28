"""Passthrough VM validation and normalization helpers."""

from __future__ import annotations

import re
from typing import Any, cast

from scripts.common.errors import require
from scripts.common.validation import as_list, as_mapping, require_non_empty_string, require_unknown_keys


def normalize_vm_passthrough(
    vm_doc: dict[str, Any],
    cluster_state: dict[str, Any],
    node_str: str,
    vm_name: str,
    ha_enabled: bool,
    ctx: str,
    passthrough_usage: dict[tuple[str, str], str],
) -> list[dict[str, Any]] | None:
    """Validate passthrough entries and return normalized device records."""
    passthrough = vm_doc.get("passthrough")
    if passthrough is None:
        return None

    devices = as_list(passthrough, f"{ctx}.passthrough")
    normalized_passthrough: list[dict[str, Any]] = []
    reserved_passthrough_devices: set[str] = set()

    for passthrough_index, device in enumerate(devices):
        dctx = f"{ctx}.passthrough[{passthrough_index}]"
        pd = as_mapping(device, dctx)
        require_unknown_keys(pd, {"mapping", "device_override", "pcie", "rombar", "xvga"}, f"{dctx}: passthrough")
        if "device_override" in pd:
            override_name = require_non_empty_string(pd.get("device_override"), f"{dctx}.device_override")
            require(re.fullmatch(r"hostpci([0-9]|1[0-5])", override_name) is not None, f"{dctx}.device_override must match hostpci0-hostpci15")
            require(override_name not in reserved_passthrough_devices, f"{dctx}: duplicate device_override {override_name}")
            reserved_passthrough_devices.add(override_name)

    assigned_passthrough_devices: set[str] = set()

    def allocate_passthrough_device() -> str:
        for device_index in range(16):
            device_name = f"hostpci{device_index}"
            if device_name in reserved_passthrough_devices or device_name in assigned_passthrough_devices:
                continue
            assigned_passthrough_devices.add(device_name)
            return device_name
        require(False, f"{ctx}: passthrough devices exhausted hostpci0-hostpci15")
        return "hostpci0"

    for passthrough_index, device in enumerate(devices):
        dctx = f"{ctx}.passthrough[{passthrough_index}]"
        pd = as_mapping(device, dctx)
        require_unknown_keys(pd, {"mapping", "device_override", "pcie", "rombar", "xvga"}, f"{dctx}: passthrough")
        if "device_override" in pd:
            device_name = require_non_empty_string(pd.get("device_override"), f"{dctx}.device_override")
        else:
            device_name = allocate_passthrough_device()
        mapping_name = pd.get("mapping")
        require(isinstance(mapping_name, str) and mapping_name, f"{dctx}: mapping must be a non-empty string")
        mapping_name_str = cast(str, mapping_name)
        mapping = cluster_state["pci_mappings"].get(mapping_name_str)
        require(mapping is not None, f"{dctx}: mapping must reference a declared PCI mapping")
        mapping_map = as_mapping(mapping, f"cluster.pci_mappings.{mapping_name_str}")
        mapping_defaults = as_mapping(mapping_map.get("defaults"), f"cluster.pci_mappings.{mapping_name_str}.defaults")
        require(mapping_map.get("ha_allowed") is False, f"{dctx}: mapping {mapping_name_str} must not allow HA")
        require(node_str in mapping_map["nodes"], f"{dctx}: VM node must be allowed by the mapping")
        usage_key = (node_str, mapping_name_str)
        previous_vm = passthrough_usage.get(usage_key)
        require(previous_vm is None, f"{dctx}: mapping {mapping_name_str} on node {node_str} is already used by VM {previous_vm}")
        for flag in ("pcie", "rombar", "xvga"):
            require(flag in pd, f"{dctx}: {flag} is required and must match mapping default {mapping_defaults.get(flag)}")
            require(pd.get(flag) == mapping_defaults.get(flag), f"{dctx}: {flag} must match mapping default {mapping_defaults.get(flag)}")
        require(ha_enabled is False, f"{dctx}: passthrough VMs must keep HA disabled")
        passthrough_usage[usage_key] = vm_name
        assigned_passthrough_devices.add(device_name)
        normalized_passthrough.append(
            {
                "device": device_name,
                "mapping": mapping_name_str,
                "pcie": pd.get("pcie"),
                "rombar": pd.get("rombar"),
                "xvga": pd.get("xvga"),
            }
        )

    return normalized_passthrough
