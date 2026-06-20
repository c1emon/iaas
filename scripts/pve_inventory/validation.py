"""Validation for cluster and VM source-of-truth YAML."""

from __future__ import annotations

import ipaddress
import re
from typing import Any, cast

from .errors import require


def as_mapping(value: Any, context: str) -> dict[str, Any]:
    """Assert that a value is a mapping and cast it for type-checkers."""
    require(isinstance(value, dict), f"{context}: expected mapping")
    return cast(dict[str, Any], value)


def as_list(value: Any, context: str) -> list[Any]:
    """Assert that a value is a list and cast it for type-checkers."""
    require(isinstance(value, list), f"{context}: expected list")
    return cast(list[Any], value)


def require_positive_int(value: Any, context: str) -> int:
    """Assert that a value is a positive integer and return it."""
    require(isinstance(value, int) and value > 0, f"{context}: must be a positive integer")
    return cast(int, value)


def require_bool(value: Any, context: str) -> bool:
    """Assert that a value is a boolean and return it."""
    require(isinstance(value, bool), f"{context}: must be a boolean")
    return cast(bool, value)


def require_unknown_keys(mapping: dict[str, Any], allowed: set[str], context: str) -> None:
    """Reject keys outside a strict schema."""
    unknown = sorted(set(mapping) - allowed)
    require(not unknown, f"{context}: unknown keys {', '.join(unknown)}")


def parse_static_ip(value: str) -> tuple[str, int, str]:
    """Split a CIDR-style static IP into host, prefix, and network string."""
    interface = ipaddress.ip_interface(value)
    return str(interface.ip), int(interface.network.prefixlen), str(interface.network)


def validate_automation(cluster_doc: dict[str, Any], storage_roles: dict[str, Any]) -> dict[str, Any]:
    """Validate cluster automation settings."""
    cluster = as_mapping(cluster_doc.get("cluster"), "cluster.cluster")
    automation = as_mapping(cluster.get("automation"), "cluster.cluster.automation")
    ansible_user = automation.get("ansible_user")
    require(isinstance(ansible_user, str) and ansible_user, "cluster: cluster.automation.ansible_user must be a non-empty string")

    cloud_init = as_mapping(automation.get("cloud_init"), "cluster.cluster.automation.cloud_init")
    defaults = cloud_init.get("defaults")
    default_values = {
        "package_update": False,
        "package_upgrade": False,
        "ssh_pwauth": False,
        "disable_root": True,
    }
    if defaults is not None:
        defaults_map = as_mapping(defaults, "cluster.cluster.automation.cloud_init.defaults")
        require_unknown_keys(defaults_map, set(default_values), "cluster: cluster.automation.cloud_init.defaults")
        for key in default_values:
            value = defaults_map.get(key)
            if value is not None:
                default_values[key] = require_bool(value, f"cluster.cluster.automation.cloud_init.defaults.{key}")
    snippet_storage_role = cloud_init.get("snippet_storage_role")
    require(isinstance(snippet_storage_role, str) and snippet_storage_role, "cluster: cluster.automation.cloud_init.snippet_storage_role must be a non-empty string")
    snippet_storage_role_str = cast(str, snippet_storage_role)
    require(snippet_storage_role_str in storage_roles, "cluster: cluster.automation.cloud_init.snippet_storage_role must reference a declared storage role")
    snippet_storage = as_mapping(storage_roles[snippet_storage_role_str], f"cluster.storage_roles.{snippet_storage_role_str}")
    require("snippets" in as_list(snippet_storage.get("content"), f"cluster.storage_roles.{snippet_storage_role_str}.content"), "cluster: cluster.automation.cloud_init.snippet_storage_role must point to storage with snippets content")

    snippet_file_prefix = cloud_init.get("snippet_file_prefix")
    require(isinstance(snippet_file_prefix, str) and re.match(r"^[A-Za-z0-9][A-Za-z0-9._-]*$", snippet_file_prefix), "cluster: cluster.automation.cloud_init.snippet_file_prefix must match ^[A-Za-z0-9][A-Za-z0-9._-]*$")

    users = as_list(cloud_init.get("users"), "cluster.cluster.automation.cloud_init.users")
    require(users, "cluster: cluster.automation.cloud_init.users must be a non-empty list")
    seen_names: set[str] = set()
    seen_env_vars: set[str] = set()
    for index, user in enumerate(users):
        uctx = f"cluster.cluster.automation.cloud_init.users[{index}]"
        user_map = as_mapping(user, uctx)
        for field in ("name", "gecos", "groups", "shell", "password_env", "public_key_env"):
            value = user_map.get(field)
            require(isinstance(value, str) and value, f"{uctx}: {field} must be a non-empty string")
        sudo = as_list(user_map.get("sudo"), f"{uctx}.sudo")
        require(sudo and all(isinstance(item, str) and item for item in sudo), f"{uctx}: sudo must be a non-empty list of non-empty strings")
        name = cast(str, user_map["name"])
        password_env = cast(str, user_map["password_env"])
        public_key_env = cast(str, user_map["public_key_env"])
        require(re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", password_env), f"{uctx}: password_env must match ^[A-Za-z_][A-Za-z0-9_]*$")
        require(re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", public_key_env), f"{uctx}: public_key_env must match ^[A-Za-z_][A-Za-z0-9_]*$")
        require(name not in seen_names, f"{uctx}: duplicate user name {name}")
        require(password_env not in seen_env_vars, f"{uctx}: duplicate environment variable {password_env}")
        require(public_key_env not in seen_env_vars, f"{uctx}: duplicate environment variable {public_key_env}")
        seen_names.add(name)
        seen_env_vars.add(password_env)
        seen_env_vars.add(public_key_env)

    return {
        "ansible_user": cast(str, ansible_user),
        "cloud_init": {
            "defaults": default_values,
            "snippet_storage_role": snippet_storage_role_str,
            "snippet_file_prefix": cast(str, snippet_file_prefix),
            "users": users,
        },
    }


def validate_cluster(cluster_doc: dict[str, Any]) -> dict[str, Any]:
    """Validate cluster policy and return normalized state for rendering."""
    require(cluster_doc.get("schema_version") == 1, "cluster: schema_version must be 1")
    cluster = as_mapping(cluster_doc.get("cluster"), "cluster.cluster")
    require(cluster.get("name") == "astra-pve", "cluster: cluster name must be astra-pve")
    require(cluster.get("default_template") == "debian_13_genericcloud", "cluster: default_template must be debian_13_genericcloud")

    reserved = as_mapping(cluster_doc.get("reserved_vm_id_ranges"), "cluster.reserved_vm_id_ranges")
    require(reserved.get("templates") == [9000, 9500], "cluster: template VMID range must be 9000-9500")
    require(reserved.get("long_lived") == [1000, 2000], "cluster: long-lived VMID range must be 1000-2000")
    require(reserved.get("ephemeral_lab") == [500, 800], "cluster: ephemeral/lab VMID range must be 500-800")

    storage_roles = as_mapping(cluster_doc.get("storage_roles"), "cluster.storage_roles")
    memory = as_mapping(storage_roles.get("memory"), "cluster.storage_roles.memory")
    images = as_mapping(storage_roles.get("images"), "cluster.storage_roles.images")
    require(memory.get("datastore") == "memory", "cluster: memory storage role must target datastore 'memory'")
    require(memory.get("content") == ["disk"], "cluster: memory storage role must carry disk content")
    require(images.get("datastore") == "images", "cluster: images storage role must target datastore 'images'")
    require(images.get("content") == ["iso", "import", "snippets"], "cluster: images storage role content mismatch")

    automation = validate_automation(cluster_doc, storage_roles)

    networks = as_mapping(cluster_doc.get("networks"), "cluster.networks")
    expected_networks = {
        "mgmt": ("vmbr0", "10.1.0.0/24", "10.1.0.254", False),
        "storage": ("storage", "10.1.1.0/24", None, False),
        "dev": ("br_dev", "10.10.0.0/24", "10.10.0.254", True),
        "prod": ("br_prod", "10.50.0.0/24", "10.50.0.254", True),
    }
    for name, (bridge, cidr, gateway, attach_vms) in expected_networks.items():
        net = as_mapping(networks.get(name), f"cluster.networks.{name}")
        require(net.get("bridge") == bridge, f"cluster: {name} bridge must be {bridge}")
        require(net.get("cidr") == cidr, f"cluster: {name} CIDR must be {cidr}")
        require(net.get("gateway") == gateway, f"cluster: {name} gateway mismatch")
        require(net.get("attach_vms") is attach_vms, f"cluster: {name} attach_vms mismatch")

    nodes = as_mapping(cluster_doc.get("nodes"), "cluster.nodes")
    require("cohe" in nodes, "cluster: cohe node must be present")
    cohe = as_mapping(nodes["cohe"], "cluster.nodes.cohe")
    require(cohe.get("mgmt_ip") == "10.1.0.72", "cluster: cohe mgmt_ip must be 10.1.0.72")
    require(cohe.get("storage_ip") == "10.1.1.72", "cluster: cohe storage_ip must be 10.1.1.72")
    require(cohe.get("ssh_host") == "cohe", "cluster: cohe ssh_host must be 'cohe'")
    if "node3" in nodes:
        node3 = as_mapping(nodes["node3"], "cluster.nodes.node3")
        require(node3.get("mgmt_ip") == "10.1.0.73", "cluster: node3 mgmt_ip must be 10.1.0.73")
        require(node3.get("storage_ip") == "10.1.1.73", "cluster: node3 storage_ip must be 10.1.1.73")

    vm_defaults = as_mapping(cluster_doc.get("vm_defaults"), "cluster.vm_defaults")
    require(vm_defaults.get("cores") == 2, "cluster: vm_defaults.cores must be 2")
    require(vm_defaults.get("memory_mib") == 2048, "cluster: vm_defaults.memory_mib must be 2048")
    require(vm_defaults.get("root_disk_gib") == 20, "cluster: vm_defaults.root_disk_gib must be 20")
    require(vm_defaults.get("cpu_type") == "host", "cluster: vm_defaults.cpu_type must be host")
    require(vm_defaults.get("bios") == "ovmf", "cluster: vm_defaults.bios must be ovmf")
    require(vm_defaults.get("machine") == "q35", "cluster: vm_defaults.machine must be q35")
    require(vm_defaults.get("clone_mode") == "full", "cluster: vm_defaults.clone_mode must be full")
    require(vm_defaults.get("scsi_controller") == "virtio-scsi-single", "cluster: vm_defaults.scsi_controller mismatch")
    require(vm_defaults.get("primary_disk") == "scsi0", "cluster: vm_defaults.primary_disk must be scsi0")
    require(vm_defaults.get("primary_nics") == 1, "cluster: vm_defaults.primary_nics must be 1")
    require(vm_defaults.get("pool") is None, "cluster: vm_defaults.pool must be null")

    templates = as_mapping(cluster_doc.get("templates"), "cluster.templates")
    require(cluster.get("default_template") in templates, "cluster: default_template must reference a declared template")
    for template_name, template_value in templates.items():
        tctx = f"cluster.templates.{template_name}"
        template = as_mapping(template_value, tctx)
        vmid = template.get("vmid")
        require(isinstance(vmid, int), f"{tctx}: vmid must be an integer")
        require(9000 <= cast(int, vmid) <= 9500, f"{tctx}: vmid must be within 9000-9500")
        require(template.get("node") in nodes, f"{tctx}: node must reference a declared PVE node")

        for field in ("name", "storage_role", "source_storage_role", "cpu_type", "bios", "machine", "clone_mode", "scsi_controller", "primary_disk"):
            value = template.get(field)
            require(isinstance(value, str) and value, f"{tctx}: {field} must be a non-empty string")

        require_positive_int(template.get("disk_size_gib"), f"{tctx}.disk_size_gib")
        require_positive_int(template.get("primary_nics"), f"{tctx}.primary_nics")

        template_storage_role = cast(str, template["storage_role"])
        require(template_storage_role in storage_roles, f"{tctx}: storage_role must reference a declared storage role")
        template_storage = as_mapping(storage_roles[template_storage_role], f"cluster.storage_roles.{template_storage_role}")
        require("disk" in as_list(template_storage.get("content"), f"cluster.storage_roles.{template_storage_role}.content"), f"{tctx}: storage_role must point to storage with disk content")

        source_storage_role = cast(str, template["source_storage_role"])
        require(source_storage_role in storage_roles, f"{tctx}: source_storage_role must reference a declared storage role")

    pci_mappings = as_mapping(cluster_doc.get("pci_mappings"), "cluster.pci_mappings")
    igpu = as_mapping(pci_mappings.get("iGpu0"), "cluster.pci_mappings.iGpu0")
    require(igpu.get("ha_allowed") is False, "cluster: iGpu0 must not allow HA")
    defaults = as_mapping(igpu.get("defaults"), "cluster.pci_mappings.iGpu0.defaults")
    require(defaults == {"pcie": True, "rombar": True, "xvga": False}, "cluster: iGpu0 defaults mismatch")
    mapping_nodes = as_mapping(igpu.get("nodes"), "cluster.pci_mappings.iGpu0.nodes")
    require({"cohe", "node3"}.issubset(mapping_nodes), "cluster: iGpu0 must be available on cohe and node3")

    return {
        "name": cluster.get("name"),
        "default_template": cluster.get("default_template"),
        "reserved_vm_id_ranges": reserved,
        "storage_roles": storage_roles,
        "automation": automation,
        "networks": networks,
        "nodes": nodes,
        "vm_defaults": vm_defaults,
        "templates": templates,
        "pci_mappings": pci_mappings,
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
    require(vms_doc.get("schema_version") == 1, "vms: schema_version must be 1")
    vms = as_list(vms_doc.get("vms"), "vms.vms")
    seen_ids: set[int] = set()
    seen_names: set[str] = set()
    seen_ips: set[str] = set()
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
        passthrough = vm_doc.get("passthrough")
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

        if passthrough is not None:
            devices = as_list(passthrough, f"{ctx}.passthrough")
            for passthrough_index, device in enumerate(devices):
                dctx = f"{ctx}.passthrough[{passthrough_index}]"
                pd = as_mapping(device, dctx)
                mapping_name = pd.get("mapping")
                require(isinstance(mapping_name, str) and mapping_name, f"{dctx}: mapping must be a non-empty string")
                mapping_name_str = cast(str, mapping_name)
                mapping = cluster_state["pci_mappings"].get(mapping_name_str)
                require(mapping is not None, f"{dctx}: mapping must reference a declared PCI mapping")
                require(node_str in as_mapping(mapping, f"cluster.pci_mappings.{mapping_name_str}")["nodes"], f"{dctx}: VM node must be allowed by the mapping")
                require(pd.get("device") == "hostpci0", f"{dctx}: device must be hostpci0 in the sample schema")
                require(pd.get("pcie") is True, f"{dctx}: pcie must be true")
                require(pd.get("rombar") is True, f"{dctx}: rombar must be true")
                require(pd.get("xvga") is False, f"{dctx}: xvga must be false")
                require(ha.get("enabled") is False, f"{dctx}: passthrough VMs must keep HA disabled")

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
                "passthrough": passthrough if passthrough is None else passthrough,
            }
        )

    return normalized
