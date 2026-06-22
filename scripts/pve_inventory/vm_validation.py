"""VM declaration validation and normalization for PVE inventory."""

from __future__ import annotations

import ipaddress
from typing import Any, cast

from .errors import require
from .validation_common import as_list, as_mapping, require_bool, require_positive_int, require_unknown_keys


def parse_static_ip(value: str) -> tuple[str, int, str]:
    """Split a CIDR-style static IP into host, prefix, and network string."""
    interface = ipaddress.ip_interface(value)
    return str(interface.ip), int(interface.network.prefixlen), str(interface.network)


def normalize_vm_resources(vm_doc: dict[str, Any], cluster_vm_defaults: dict[str, Any], ctx: str) -> dict[str, int]:
    """Resolve effective VM resource quantities."""
    resources = vm_doc.get("resources")
    effective = {
        "cores": require_positive_int(cluster_vm_defaults["cores"], "cluster.vm_defaults.cores"),
        "memory_mib": require_positive_int(cluster_vm_defaults["memory_mib"], "cluster.vm_defaults.memory_mib"),
        "root_disk_gib": require_positive_int(cluster_vm_defaults["root_disk_gib"], "cluster.vm_defaults.root_disk_gib"),
    }
    if resources is None:
        return effective

    resources_map = as_mapping(resources, f"{ctx}.resources")
    require_unknown_keys(resources_map, {"cores", "memory_mib", "root_disk_gib"}, f"{ctx}: resources")
    for key in effective:
        value = resources_map.get(key)
        if value is not None:
            effective[key] = require_positive_int(value, f"{ctx}.resources.{key}")
    return effective


def normalize_vm_storage(vm_doc: dict[str, Any], template: dict[str, Any], cluster_storage_roles: dict[str, Any], ctx: str) -> dict[str, str]:
    """Resolve effective VM disk storage."""
    storage = vm_doc.get("storage")
    storage_role = cast(str, template["storage_role"])
    if storage is not None:
        storage_map = as_mapping(storage, f"{ctx}.storage")
        require_unknown_keys(storage_map, {"disk_role"}, f"{ctx}: storage")
        disk_role = storage_map.get("disk_role")
        require(isinstance(disk_role, str) and disk_role, f"{ctx}.storage.disk_role must be a non-empty string")
        storage_role = cast(str, disk_role)

    require(storage_role in cluster_storage_roles, f"{ctx}: storage role {storage_role} must reference a declared storage role")
    role = as_mapping(cluster_storage_roles[storage_role], f"cluster.storage_roles.{storage_role}")
    require("disk" in as_list(role.get("content"), f"cluster.storage_roles.{storage_role}.content"), f"{ctx}: storage role {storage_role} must include disk content")
    datastore = role.get("datastore")
    require(isinstance(datastore, str) and datastore, f"{ctx}: storage role {storage_role} must define a non-empty datastore")
    return {"disk_role": storage_role, "disk_datastore_id": cast(str, datastore)}


def normalize_vm_boot(vm_doc: dict[str, Any], lifecycle_class: str, ctx: str) -> dict[str, bool]:
    """Resolve effective VM boot behavior."""
    boot = vm_doc.get("boot")
    effective = {
        "started": True,
        "on_boot": lifecycle_class == "long_lived",
    }
    if boot is None:
        return effective

    boot_map = as_mapping(boot, f"{ctx}.boot")
    require_unknown_keys(boot_map, {"started", "on_boot"}, f"{ctx}: boot")
    for key in effective:
        value = boot_map.get(key)
        if value is not None:
            effective[key] = require_bool(value, f"{ctx}.boot.{key}")
    return effective


def validate_vms(vms_doc: dict[str, Any], cluster_state: dict[str, Any]) -> list[dict[str, Any]]:
    """Validate VM declarations and return normalized VM records."""
    from .passthrough import normalize_vm_passthrough

    require(vms_doc.get("schema_version") == 1, "vms: schema_version must be 1")
    vms = as_list(vms_doc.get("vms"), "vms.vms")
    seen_ids: set[int] = set()
    seen_names: set[str] = set()
    seen_ips: set[str] = set()
    passthrough_usage: dict[tuple[str, str], str] = {}
    normalized: list[dict[str, Any]] = []

    for index, vm in enumerate(vms):
        ctx = f"vms.vms[{index}]"
        vm_doc = as_mapping(vm, ctx)
        name = vm_doc.get("name")
        vmid = vm_doc.get("vmid")
        lifecycle = vm_doc.get("lifecycle_class")
        node = vm_doc.get("node")
        network_name = vm_doc.get("network")
        static_ip = vm_doc.get("static_ip")
        gateway = vm_doc.get("gateway")
        dns = as_list(vm_doc.get("dns"), f"{ctx}.dns")
        ansible_groups = as_list(vm_doc.get("ansible_groups"), f"{ctx}.ansible_groups")
        tags = as_list(vm_doc.get("tags"), f"{ctx}.tags")
        ha = as_mapping(vm_doc.get("ha"), f"{ctx}.ha")
        pool = vm_doc.get("pool")
        template_name = vm_doc.get("template", cluster_state["default_template"])

        require(isinstance(name, str) and name, f"{ctx}: name must be a non-empty string")
        name_str = cast(str, name)
        require(name_str not in seen_names, f"{ctx}: duplicate VM name {name_str}")
        seen_names.add(name_str)

        require(isinstance(vmid, int), f"{ctx}: vmid must be an integer")
        vmid_int = cast(int, vmid)
        require(vmid_int not in seen_ids, f"{ctx}: duplicate VMID {vmid_int}")
        seen_ids.add(vmid_int)

        require(isinstance(lifecycle, str) and lifecycle in {"ephemeral_lab", "long_lived"}, f"{ctx}: lifecycle_class must be ephemeral_lab or long_lived")
        lifecycle_str = cast(str, lifecycle)
        if lifecycle_str == "ephemeral_lab":
            require(500 <= vmid_int <= 800, f"{ctx}: ephemeral_lab VMIDs must be within 500-800")
        if lifecycle_str == "long_lived":
            require(1000 <= vmid_int <= 2000, f"{ctx}: long_lived VMIDs must be within 1000-2000")

        require(isinstance(node, str) and node in cluster_state["nodes"], f"{ctx}: node must reference a declared PVE node")
        node_str = cast(str, node)

        require(isinstance(network_name, str), f"{ctx}: network must be a string")
        network_name_str = cast(str, network_name)
        network = cluster_state["networks"].get(network_name_str)
        require(network is not None, f"{ctx}: network must reference a declared network")
        network = cast(dict[str, Any], network)
        require(network.get("attach_vms") is True, f"{ctx}: network {network_name_str} is not attachable for VMs")

        require(isinstance(static_ip, str), f"{ctx}: static_ip must be a string")
        host_ip, prefix_length, network_cidr = parse_static_ip(cast(str, static_ip))
        cidr = ipaddress.ip_network(network["cidr"], strict=False)
        require(ipaddress.ip_address(host_ip) in cidr, f"{ctx}: static_ip must be inside {network_name_str} ({network['cidr']})")
        require(host_ip not in seen_ips, f"{ctx}: duplicate static IP {host_ip}")
        seen_ips.add(host_ip)
        require(gateway == network.get("gateway"), f"{ctx}: gateway must match the selected network")
        require(dns == [network.get("dns")], f"{ctx}: dns must match the selected network")
        require(ansible_groups, f"{ctx}: ansible_groups must not be empty")
        require(tags, f"{ctx}: tags must not be empty")
        require(isinstance(ha.get("enabled"), bool) and ha.get("enabled") is False, f"{ctx}: HA must stay disabled in section 2")
        require(ha.get("group") is None, f"{ctx}: HA group must be null until HA automation is implemented")
        require(ha.get("state") is None, f"{ctx}: HA state must be null until HA automation is implemented")

        require(pool is None or isinstance(pool, str), f"{ctx}: pool must be null or a string")
        require(template_name in cluster_state["templates"], f"{ctx}: template must reference a declared cluster template")
        template = as_mapping(cluster_state["templates"][template_name], f"cluster.templates.{template_name}")
        template_storage_role = cast(str, template.get("storage_role"))
        require(template_storage_role in cluster_state["storage_roles"], f"{ctx}: template storage_role must reference a declared storage role")
        template_storage = as_mapping(cluster_state["storage_roles"][template_storage_role], f"cluster.storage_roles.{template_storage_role}")
        require("disk" in as_list(template_storage.get("content"), f"cluster.storage_roles.{template_storage_role}.content"), f"{ctx}: template storage_role must include disk content")

        resources = normalize_vm_resources(vm_doc, cluster_state["vm_defaults"], ctx)
        storage = normalize_vm_storage(vm_doc, template, cluster_state["storage_roles"], ctx)
        boot = normalize_vm_boot(vm_doc, lifecycle_str, ctx)
        require(resources["root_disk_gib"] >= cast(int, template.get("disk_size_gib")), f"{ctx}: root_disk_gib must be at least {template.get('disk_size_gib')} GiB because PVE cannot shrink disks")

        normalized_passthrough = normalize_vm_passthrough(
            vm_doc,
            cluster_state,
            node_str,
            name_str,
            cast(bool, ha.get("enabled")),
            ctx,
            passthrough_usage,
        )

        normalized.append(
            {
                "name": name_str,
                "vmid": vmid_int,
                "lifecycle_class": lifecycle_str,
                "node": node_str,
                "network": {
                    "name": network_name_str,
                    "bridge": network.get("bridge"),
                    "cidr": network.get("cidr"),
                    "gateway": network.get("gateway"),
                    "dns": network.get("dns"),
                    "attach_vms": network.get("attach_vms"),
                },
                "static_ip": cast(str, static_ip),
                "ip_address": host_ip,
                "prefix_length": prefix_length,
                "network_cidr": network_cidr,
                "gateway": gateway,
                "dns": dns,
                "ansible_groups": list(ansible_groups),
                "tags": list(tags),
                "pool": pool,
                "ha": {"enabled": False, "group": None, "state": None},
                "resources": resources,
                "boot": boot,
                "template": {
                    "name": template_name,
                    "vmid": template.get("vmid"),
                    "vm_name": template.get("name"),
                    "node": template.get("node"),
                    "storage_role": template_storage_role,
                    "disk_size_gib": template.get("disk_size_gib"),
                    "cpu_type": template.get("cpu_type"),
                    "bios": template.get("bios"),
                    "machine": template.get("machine"),
                    "scsi_controller": template.get("scsi_controller"),
                    "primary_disk": template.get("primary_disk"),
                },
                "storage": storage,
                "passthrough": normalized_passthrough,
            }
        )

    return normalized
