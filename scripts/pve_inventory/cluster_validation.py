"""Cluster-level validation for PVE source-of-truth YAML."""

from __future__ import annotations

import ipaddress
import re
from typing import Any, cast

from scripts.common.errors import require
from scripts.common.validation import as_list, as_mapping, require_bool, require_non_empty_string, require_positive_int, require_unknown_keys, require_url_like


def validate_automation(cluster_doc: dict[str, Any], storage_roles: dict[str, Any], templates: dict[str, Any], networks: dict[str, Any]) -> dict[str, Any]:
    """Validate cluster automation settings."""
    cluster = as_mapping(cluster_doc.get("cluster"), "cluster.cluster")
    automation = as_mapping(cluster.get("automation"), "cluster.cluster.automation")
    ansible_user = require_non_empty_string(automation.get("ansible_user"), "cluster: cluster.automation.ansible_user")

    template_build = as_mapping(automation.get("template_build"), "cluster.cluster.automation.template_build")
    require_unknown_keys(
        template_build,
        {
            "template_key",
            "image_url",
            "image_sha512",
            "image_url_prefix",
            "import_storage_role",
            "disk_storage_role",
            "build_domain",
            "apt_mirror",
            "apt_security_mirror",
            "timezone",
            "locale",
            "ciuser",
            "nameserver",
            "build_bridge",
        },
        "cluster: cluster.automation.template_build",
    )

    template_key = require_non_empty_string(template_build.get("template_key"), "cluster: cluster.automation.template_build.template_key")
    require(template_key in templates, "cluster: cluster.automation.template_build.template_key must reference a declared template")
    template = as_mapping(templates[template_key], f"cluster.templates.{template_key}")

    image_url = require_url_like(template_build.get("image_url"), "cluster: cluster.automation.template_build.image_url")
    image_url_prefix = require_url_like(template_build.get("image_url_prefix"), "cluster: cluster.automation.template_build.image_url_prefix")
    require(image_url.startswith(image_url_prefix), "cluster: cluster.automation.template_build.image_url must start with image_url_prefix")
    image_sha512 = require_non_empty_string(template_build.get("image_sha512"), "cluster: cluster.automation.template_build.image_sha512")
    require(re.fullmatch(r"[A-Fa-f0-9]{128}", image_sha512) is not None, "cluster: cluster.automation.template_build.image_sha512 must be 128 hex characters")

    import_storage_role = require_non_empty_string(template_build.get("import_storage_role"), "cluster: cluster.automation.template_build.import_storage_role")
    require(import_storage_role in storage_roles, "cluster: cluster.automation.template_build.import_storage_role must reference a declared storage role")
    import_storage = as_mapping(storage_roles[import_storage_role], f"cluster.storage_roles.{import_storage_role}")
    import_content = set(as_list(import_storage.get("content"), f"cluster.storage_roles.{import_storage_role}.content"))
    require({"import", "snippets"}.issubset(import_content), "cluster: cluster.automation.template_build.import_storage_role must include import and snippets content")

    disk_storage_role = require_non_empty_string(template_build.get("disk_storage_role"), "cluster: cluster.automation.template_build.disk_storage_role")
    require(disk_storage_role in storage_roles, "cluster: cluster.automation.template_build.disk_storage_role must reference a declared storage role")
    disk_storage = as_mapping(storage_roles[disk_storage_role], f"cluster.storage_roles.{disk_storage_role}")
    require("disk" in as_list(disk_storage.get("content"), f"cluster.storage_roles.{disk_storage_role}.content"), "cluster: cluster.automation.template_build.disk_storage_role must include disk content")

    build_domain = require_non_empty_string(template_build.get("build_domain"), "cluster: cluster.automation.template_build.build_domain")
    require(re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?", build_domain) is not None, "cluster: cluster.automation.template_build.build_domain must look like a hostname")
    apt_mirror = require_url_like(template_build.get("apt_mirror"), "cluster: cluster.automation.template_build.apt_mirror")
    apt_security_mirror = require_url_like(template_build.get("apt_security_mirror"), "cluster: cluster.automation.template_build.apt_security_mirror")
    timezone = require_non_empty_string(template_build.get("timezone"), "cluster: cluster.automation.template_build.timezone")
    locale = require_non_empty_string(template_build.get("locale"), "cluster: cluster.automation.template_build.locale")
    ciuser = require_non_empty_string(template_build.get("ciuser"), "cluster: cluster.automation.template_build.ciuser")
    nameserver = require_non_empty_string(template_build.get("nameserver"), "cluster: cluster.automation.template_build.nameserver")
    try:
        ipaddress.ip_address(nameserver)
    except ValueError:
        require(False, "cluster: cluster.automation.template_build.nameserver must be a valid IP address")

    build_bridge = require_non_empty_string(template_build.get("build_bridge"), "cluster: cluster.automation.template_build.build_bridge")
    build_network = next((net for net in networks.values() if net.get("bridge") == build_bridge), None)
    require(build_network is not None, "cluster: cluster.automation.template_build.build_bridge must reference a declared network bridge")
    build_network_map = cast(dict[str, Any], build_network)
    require(build_network_map.get("attach_vms") is True, "cluster: cluster.automation.template_build.build_bridge must reference an attachable network bridge")

    cloud_init = as_mapping(automation.get("cloud_init"), "cluster.cluster.automation.cloud_init")
    require_unknown_keys(
        cloud_init,
        {
            "defaults",
            "drive_storage_role",
            "snippet_storage_role",
            "snippet_file_prefix",
            "users",
        },
        "cluster: cluster.automation.cloud_init",
    )
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

    drive_storage_role = require_non_empty_string(cloud_init.get("drive_storage_role"), "cluster: cluster.automation.cloud_init.drive_storage_role must be a non-empty string")
    require(drive_storage_role in storage_roles, "cluster: cluster.automation.cloud_init.drive_storage_role must reference a declared storage role")
    drive_storage = as_mapping(storage_roles[drive_storage_role], f"cluster.storage_roles.{drive_storage_role}")
    require("disk" in as_list(drive_storage.get("content"), f"cluster.storage_roles.{drive_storage_role}.content"), "cluster: cluster.automation.cloud_init.drive_storage_role must point to storage with disk content")

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
        "ansible_user": ansible_user,
        "template_build": {
            "template_key": template_key,
            "template_vmid": template.get("vmid"),
            "template_name": template.get("name"),
            "image_url": image_url,
            "image_sha512": image_sha512,
            "image_url_prefix": image_url_prefix,
            "import_storage_role": import_storage_role,
            "import_storage": cast(str, import_storage.get("datastore")),
            "disk_storage_role": disk_storage_role,
            "disk_storage": cast(str, disk_storage.get("datastore")),
            "build_domain": build_domain,
            "apt_mirror": apt_mirror,
            "apt_security_mirror": apt_security_mirror,
            "timezone": timezone,
            "locale": locale,
            "ciuser": ciuser,
            "nameserver": nameserver,
            "build_bridge": build_bridge,
        },
        "cloud_init": {
            "defaults": default_values,
            "drive_storage_role": drive_storage_role,
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

    templates = as_mapping(cluster_doc.get("templates"), "cluster.templates")
    automation = validate_automation(cluster_doc, storage_roles, templates, networks)

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
