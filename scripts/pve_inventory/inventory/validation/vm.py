"""VM declaration validation and normalization for PVE inventory."""

from __future__ import annotations

import ipaddress
import re
from typing import Any, cast

from scripts.common.errors import ValidationError, require
from scripts.common.validation import as_list, as_mapping, require_bool, require_positive_int, require_unknown_keys


DNS_LABEL_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")
ANSIBLE_GROUP_RE = re.compile(r"^[a-z][a-z0-9_]*$")
PVE_TAG_RE = re.compile(r"^[a-z0-9]+(?:[._-][a-z0-9]+)*$")
NIC_NAME_RE = DNS_LABEL_RE
NIC_ROLE_RE = DNS_LABEL_RE
MAC_ADDRESS_RE = re.compile(r"^[0-9A-Fa-f]{2}(?::[0-9A-Fa-f]{2}){5}$")
LINUX_INTERFACE_NAME_MAX_LENGTH = 15


def parse_static_ip(value: str) -> tuple[str, int, str]:
    """Split a CIDR-style static IP into host, prefix, and network string."""
    interface = ipaddress.ip_interface(value)
    return str(interface.ip), int(interface.network.prefixlen), str(interface.network)


def parse_mac_address(value: str, context: str) -> str:
    """Validate and normalize a MAC address string."""
    require(isinstance(value, str) and value, f"{context}: must be a non-empty string")
    require(MAC_ADDRESS_RE.fullmatch(value) is not None, f"{context}: must be a MAC address in colon-separated hex format")
    return value.lower()


def _require_pattern(value: Any, context: str, pattern: re.Pattern[str], description: str) -> str:
    text = value if isinstance(value, str) else None
    require(isinstance(text, str) and text, f"{context}: must be a non-empty string")
    assert text is not None
    require(pattern.fullmatch(text) is not None, f"{context}: must be {description}")
    return text


def _normalize_string_list(value: Any, context: str, item_description: str, pattern: re.Pattern[str], duplicate_label: str) -> list[str]:
    items = as_list(value, context)
    require(items, f"{context}: must not be empty")
    normalized: list[str] = []
    seen: set[str] = set()
    for index, item in enumerate(items):
        item_context = f"{context}[{index}]"
        text = _require_pattern(item, item_context, pattern, item_description)
        require(text not in seen, f"{context}: duplicate {duplicate_label} {text}")
        seen.add(text)
        normalized.append(text)
    return normalized


def _normalize_dns_list(value: Any, context: str) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        raw_items: list[Any] = [value]
    else:
        raw_items = as_list(value, context)
    normalized: list[str] = []
    seen: set[str] = set()
    for index, item in enumerate(raw_items):
        item_context = f"{context}[{index}]"
        require(isinstance(item, str) and item, f"{item_context}: must be a non-empty string")
        try:
            ipaddress.ip_address(item)
        except ValueError as exc:
            raise ValidationError(f"{item_context}: must be a valid IP address") from exc
        require(item not in seen, f"{context}: duplicate DNS entry {item}")
        seen.add(item)
        normalized.append(item)
    return normalized


def _normalize_nic_name(value: Any, context: str) -> str:
    name = _require_pattern(value, context, NIC_NAME_RE, "a lower-case DNS-label-safe value")
    require(
        len(name) <= LINUX_INTERFACE_NAME_MAX_LENGTH,
        f"{context}: must be at most {LINUX_INTERFACE_NAME_MAX_LENGTH} characters because it becomes a Linux interface name",
    )
    return name


def _normalize_nic_role(value: Any, context: str) -> str:
    return _require_pattern(value, context, NIC_ROLE_RE, "a lower-case DNS-label-safe value")


def _normalize_nic(
    nic_doc: dict[str, Any],
    cluster_state: dict[str, Any],
    ctx: str,
    seen_ips: set[str],
    seen_macs: set[str],
) -> dict[str, Any]:
    require_unknown_keys(nic_doc, {"name", "role", "network", "macaddr", "mac_address", "static_ip", "gateway", "dns", "default_route", "ansible_connection"}, f"{ctx}: nic")

    name = _normalize_nic_name(nic_doc.get("name"), f"{ctx}.name")
    role = _normalize_nic_role(nic_doc.get("role"), f"{ctx}.role")
    network_name = nic_doc.get("network")
    require(isinstance(network_name, str) and network_name, f"{ctx}.network must be a non-empty string")
    network_name_str = cast(str, network_name)
    network = cluster_state["networks"].get(network_name_str)
    require(network is not None, f"{ctx}: network must reference a declared network")
    network = cast(dict[str, Any], network)
    require(network.get("attach_vms") is True, f"{ctx}: network {network_name_str} is not attachable for VMs")

    mac_value = nic_doc.get("mac_address", nic_doc.get("macaddr"))
    require(mac_value is not None, f"{ctx}: macaddr must be provided")
    mac_address = parse_mac_address(cast(str, mac_value), f"{ctx}.macaddr")
    require(mac_address not in seen_macs, f"{ctx}.macaddr: duplicate MAC {mac_address}")
    seen_macs.add(mac_address)

    static_ip = nic_doc.get("static_ip")
    require(isinstance(static_ip, str), f"{ctx}: static_ip must be a string")
    try:
        host_ip, prefix_length, network_cidr = parse_static_ip(cast(str, static_ip))
    except ValueError as exc:
        raise ValidationError(f"{ctx}.static_ip: must be a valid CIDR-style IP interface") from exc
    cidr = ipaddress.ip_network(network["cidr"], strict=False)
    require(prefix_length == cidr.prefixlen, f"{ctx}.static_ip: must use prefix /{cidr.prefixlen}")
    ip_addr = ipaddress.ip_address(host_ip)
    require(ip_addr.version == cidr.version, f"{ctx}.static_ip: address family must match {network_name_str} ({network['cidr']})")
    require(ip_addr in cidr, f"{ctx}.static_ip: must be inside {network_name_str} ({network['cidr']})")
    require(ip_addr != cidr.network_address, f"{ctx}.static_ip: must not be the network address {cidr.network_address}")
    require(ip_addr != cidr.broadcast_address, f"{ctx}.static_ip: must not be the broadcast address {cidr.broadcast_address}")
    require(host_ip not in seen_ips, f"{ctx}.static_ip: duplicate IP {host_ip}")
    seen_ips.add(host_ip)

    gateway = nic_doc.get("gateway")
    default_route_raw = nic_doc.get("default_route")
    if default_route_raw is not None:
        default_route_raw = require_bool(default_route_raw, f"{ctx}.default_route")
    if gateway is not None:
        require(isinstance(gateway, str) and gateway, f"{ctx}.gateway must be a non-empty string")
        try:
            ipaddress.ip_address(gateway)
        except ValueError as exc:
            raise ValidationError(f"{ctx}.gateway: must be a valid IP address") from exc
        require(gateway == network.get("gateway"), f"{ctx}: gateway must match the selected network")
        default_route = True
    else:
        default_route = bool(default_route_raw) if default_route_raw is not None else False
        require(not default_route, f"{ctx}.default_route: default_route true requires gateway")

    dns = _normalize_dns_list(nic_doc.get("dns"), f"{ctx}.dns")

    ansible_connection_raw = nic_doc.get("ansible_connection")
    ansible_connection = require_bool(ansible_connection_raw, f"{ctx}.ansible_connection") if ansible_connection_raw is not None else False

    return {
        "name": name,
        "role": role,
        "network": {
            "name": network_name_str,
            "bridge": network.get("bridge"),
            "cidr": network.get("cidr"),
            "gateway": network.get("gateway"),
            "dns": network.get("dns"),
            "attach_vms": network.get("attach_vms"),
        },
        "mac_address": mac_address,
        "static_ip": cast(str, static_ip),
        "ip_address": host_ip,
        "prefix_length": prefix_length,
        "network_cidr": network_cidr,
        "gateway": gateway,
        "default_route": default_route,
        "ansible_connection": ansible_connection,
        "dns": dns,
    }


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
    seen_macs: set[str] = set()
    passthrough_usage: dict[tuple[str, str], str] = {}
    normalized: list[dict[str, Any]] = []

    for index, vm in enumerate(vms):
        ctx = f"vms.vms[{index}]"
        vm_doc = as_mapping(vm, ctx)
        name = vm_doc.get("name")
        vmid = vm_doc.get("vmid")
        lifecycle = vm_doc.get("lifecycle_class")
        node = vm_doc.get("node")
        raw_nics = vm_doc.get("nics")
        ansible_groups = _normalize_string_list(vm_doc.get("ansible_groups"), f"{ctx}.ansible_groups", "a lower-case Ansible-safe identifier", ANSIBLE_GROUP_RE, "ansible_groups value")
        tags = _normalize_string_list(vm_doc.get("tags"), f"{ctx}.tags", "a lower-case PVE tag token", PVE_TAG_RE, "tag")
        ha = as_mapping(vm_doc.get("ha"), f"{ctx}.ha")
        pool = vm_doc.get("pool")
        template_name = vm_doc.get("template", cluster_state["default_template"])

        name_str = _require_pattern(name, f"{ctx}.name", DNS_LABEL_RE, "a lower-case DNS-label-safe value")
        require(name_str not in seen_names, f"{ctx}: duplicate VM name {name_str}")
        seen_names.add(name_str)

        require(isinstance(vmid, int), f"{ctx}: vmid must be an integer")
        vmid_int = cast(int, vmid)
        require(vmid_int not in seen_ids, f"{ctx}: duplicate VMID {vmid_int}")
        seen_ids.add(vmid_int)

        require(isinstance(lifecycle, str) and lifecycle in {"ephemeral_lab", "long_lived"}, f"{ctx}: lifecycle_class must be ephemeral_lab or long_lived")
        lifecycle_str = cast(str, lifecycle)
        lifecycle_range = cluster_state["reserved_vm_id_ranges"][lifecycle_str]
        require(
            lifecycle_range[0] <= vmid_int <= lifecycle_range[1],
            f"{ctx}: {lifecycle_str} VMID must be within the declared {lifecycle_str} range",
        )

        require(isinstance(node, str) and node in cluster_state["nodes"], f"{ctx}: node must reference a declared PVE node")
        node_str = cast(str, node)

        require("nics" in vm_doc, f"{ctx}: nics must be provided")
        legacy_fields = [field for field in ("network", "static_ip", "gateway", "dns") if field in vm_doc]
        require(not legacy_fields, f"{ctx}: legacy NIC fields are not supported: {', '.join(legacy_fields)}")
        nic_entries = as_list(raw_nics, f"{ctx}.nics")
        nics = [
            _normalize_nic(cast(dict[str, Any], as_mapping(nic, f"{ctx}.nics[{nic_index}]")), cluster_state, f"{ctx}.nics[{nic_index}]", seen_ips, seen_macs)
            for nic_index, nic in enumerate(nic_entries)
        ]
        nic_names = [nic["name"] for nic in nics]
        require(len(set(nic_names)) == len(nic_names), f"{ctx}.nics: duplicate NIC name")
        default_route_nics = [nic for nic in nics if nic["default_route"]]
        require(len(default_route_nics) <= 1, f"{ctx}.nics: explicit NIC declarations may have at most one default route")
        ansible_connection_nics = [nic for nic in nics if nic["ansible_connection"]]
        require(len(ansible_connection_nics) <= 1, f"{ctx}.nics: explicit NIC declarations may have at most one ansible_connection NIC")
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

        vm_record: dict[str, Any] = {
            "name": name_str,
            "vmid": vmid_int,
            "lifecycle_class": lifecycle_str,
            "node": node_str,
            "nics": nics,
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
        normalized.append(vm_record)

    return normalized
