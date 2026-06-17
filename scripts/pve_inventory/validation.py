"""Validation for cluster and VM source-of-truth YAML."""

from __future__ import annotations

import ipaddress
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


def parse_static_ip(value: str) -> tuple[str, int, str]:
    """Split a CIDR-style static IP into host, prefix, and network string."""
    interface = ipaddress.ip_interface(value)
    return str(interface.ip), int(interface.network.prefixlen), str(interface.network)


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
    require(list(templates) == ["debian_13_genericcloud"], "cluster: exactly one template is expected in section 2")
    template = as_mapping(templates["debian_13_genericcloud"], "cluster.templates.debian_13_genericcloud")
    vmid = template.get("vmid")
    require(isinstance(vmid, int), "cluster.templates.debian_13_genericcloud: vmid must be an integer")
    require(9000 <= cast(int, vmid) <= 9500, "cluster.templates.debian_13_genericcloud: vmid must be within 9000-9500")
    require(template.get("node") in nodes, "cluster.templates.debian_13_genericcloud: node must reference a declared PVE node")
    require(template.get("storage_role") == "memory", "cluster.templates.debian_13_genericcloud: storage_role must be memory")
    require(template.get("source_storage_role") == "images", "cluster.templates.debian_13_genericcloud: source_storage_role must be images")
    require(template.get("disk_size_gib") == 20, "cluster.templates.debian_13_genericcloud: disk_size_gib must be 20")
    require(template.get("cpu_type") == "host", "cluster.templates.debian_13_genericcloud: cpu_type must be host")
    require(template.get("bios") == "ovmf", "cluster.templates.debian_13_genericcloud: bios must be ovmf")
    require(template.get("machine") == "q35", "cluster.templates.debian_13_genericcloud: machine must be q35")
    require(template.get("clone_mode") == "full", "cluster.templates.debian_13_genericcloud: clone_mode must be full")
    require(template.get("scsi_controller") == "virtio-scsi-single", "cluster.templates.debian_13_genericcloud: scsi_controller mismatch")
    require(template.get("primary_disk") == "scsi0", "cluster.templates.debian_13_genericcloud: primary_disk must be scsi0")
    require(template.get("primary_nics") == 1, "cluster.templates.debian_13_genericcloud: primary_nics must be 1")

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
        "networks": networks,
        "nodes": nodes,
        "vm_defaults": vm_defaults,
        "templates": templates,
        "pci_mappings": pci_mappings,
    }


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
                "template": {
                    "name": template_name,
                    "vmid": template.get("vmid"),
                    "vm_name": template.get("name"),
                },
                "vm_defaults": cluster_state["vm_defaults"],
                "passthrough": passthrough if passthrough is None else passthrough,
            }
        )

    return normalized
