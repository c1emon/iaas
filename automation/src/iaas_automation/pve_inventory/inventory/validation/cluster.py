"""Cluster-level validation for PVE source-of-truth YAML."""

from __future__ import annotations

import ipaddress
import re
from typing import Any, cast

from iaas_automation.common.errors import ValidationError, require
from iaas_automation.common.validation import as_list, as_mapping, require_bool, require_non_empty_string, require_positive_int, require_unknown_keys, require_url_like


PVE_VMID_MIN = 100
PVE_VMID_MAX = 999_999_999
VMID_RANGE_NAMES = {"templates", "long_lived", "ephemeral_lab"}
PVE_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


def _require_ip(value: Any, context: str) -> str:
    text = require_non_empty_string(value, context)
    try:
        ipaddress.ip_address(text)
    except ValueError as exc:
        raise ValidationError(f"{context}: must be a valid IP address") from exc
    return text


def _validate_vmid_ranges(value: Any) -> dict[str, list[int]]:
    ranges = as_mapping(value, "cluster.reserved_vm_id_ranges")
    require_unknown_keys(ranges, VMID_RANGE_NAMES, "cluster.reserved_vm_id_ranges")
    normalized: dict[str, list[int]] = {}
    for name in sorted(VMID_RANGE_NAMES):
        bounds = as_list(ranges.get(name), f"cluster.reserved_vm_id_ranges.{name}")
        require(len(bounds) == 2, f"cluster.reserved_vm_id_ranges.{name}: must contain exactly two bounds")
        lower, upper = bounds
        require(
            isinstance(lower, int) and not isinstance(lower, bool) and isinstance(upper, int) and not isinstance(upper, bool),
            f"cluster.reserved_vm_id_ranges.{name}: bounds must be integers",
        )
        lower_int, upper_int = cast(int, lower), cast(int, upper)
        require(PVE_VMID_MIN <= lower_int <= upper_int <= PVE_VMID_MAX, f"cluster.reserved_vm_id_ranges.{name}: bounds must be within {PVE_VMID_MIN}-{PVE_VMID_MAX}")
        normalized[name] = [lower_int, upper_int]

    names = sorted(normalized)
    for index, left_name in enumerate(names):
        left = normalized[left_name]
        for right_name in names[index + 1 :]:
            right = normalized[right_name]
            require(left[1] < right[0] or right[1] < left[0], f"cluster.reserved_vm_id_ranges.{left_name} and {right_name}: ranges must not overlap")
    return normalized


def _in_range(value: int, bounds: list[int]) -> bool:
    return bounds[0] <= value <= bounds[1]


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
    name = require_non_empty_string(cluster.get("name"), "cluster.cluster.name")
    require(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", name) is not None, "cluster.cluster.name must be PVE-safe")
    default_template = require_non_empty_string(cluster.get("default_template"), "cluster.cluster.default_template")

    reserved = _validate_vmid_ranges(cluster_doc.get("reserved_vm_id_ranges"))

    storage_roles = as_mapping(cluster_doc.get("storage_roles"), "cluster.storage_roles")
    require(storage_roles, "cluster.storage_roles must be a non-empty mapping")
    datastores: set[str] = set()
    for role_name, role_value in storage_roles.items():
        role_context = f"cluster.storage_roles.{role_name}"
        role = as_mapping(role_value, role_context)
        datastore = require_non_empty_string(role.get("datastore"), f"{role_context}.datastore")
        require(datastore not in datastores, f"{role_context}.datastore: datastore is already used by another role")
        datastores.add(datastore)
        content = as_list(role.get("content"), f"{role_context}.content")
        require(content and all(isinstance(item, str) and item for item in content), f"{role_context}.content: must be a non-empty list of strings")

    networks = as_mapping(cluster_doc.get("networks"), "cluster.networks")
    require(networks, "cluster.networks must be a non-empty mapping")
    for network_name, network_value in networks.items():
        network_context = f"cluster.networks.{network_name}"
        network = as_mapping(network_value, network_context)
        require_non_empty_string(network.get("bridge"), f"{network_context}.bridge")
        cidr = require_non_empty_string(network.get("cidr"), f"{network_context}.cidr")
        try:
            network_obj = ipaddress.ip_network(cidr, strict=False)
        except ValueError as exc:
            raise ValidationError(f"{network_context}.cidr: must be a valid network") from exc
        gateway = network.get("gateway")
        if gateway is not None:
            gateway_text = _require_ip(gateway, f"{network_context}.gateway")
            require(ipaddress.ip_address(gateway_text) in network_obj, f"{network_context}.gateway: must belong to the declared network")
        dns = network.get("dns")
        if dns is not None:
            dns_values = dns if isinstance(dns, list) else [dns]
            require(dns_values and all(isinstance(item, str) for item in dns_values), f"{network_context}.dns: must be an IP address or list of IP addresses")
            for dns_index, dns_value in enumerate(dns_values):
                _require_ip(dns_value, f"{network_context}.dns[{dns_index}]")
        require(isinstance(network.get("attach_vms"), bool), f"{network_context}.attach_vms: must be a boolean")

    templates = as_mapping(cluster_doc.get("templates"), "cluster.templates")
    require(templates, "cluster.templates must be a non-empty mapping")
    require(default_template in templates, "cluster: default_template must reference a declared template")
    automation = validate_automation(cluster_doc, storage_roles, templates, networks)

    nodes = as_mapping(cluster_doc.get("nodes"), "cluster.nodes")
    require(nodes, "cluster.nodes must be a non-empty mapping")
    node_ips: set[str] = set()
    node_ssh_hosts: set[str] = set()
    for node_name, node_value in nodes.items():
        node_context = f"cluster.nodes.{node_name}"
        node = as_mapping(node_value, node_context)
        for address_field in ("mgmt_ip", "storage_ip"):
            address = _require_ip(node.get(address_field), f"{node_context}.{address_field}")
            require(address not in node_ips, f"{node_context}.{address_field}: duplicate node address")
            node_ips.add(address)
        ssh_host = require_non_empty_string(node.get("ssh_host"), f"{node_context}.ssh_host")
        require(ssh_host not in node_ssh_hosts, f"{node_context}.ssh_host: duplicate SSH host")
        node_ssh_hosts.add(ssh_host)

    vm_defaults = as_mapping(cluster_doc.get("vm_defaults"), "cluster.vm_defaults")
    for field in ("cores", "memory_mib", "root_disk_gib", "primary_nics"):
        require_positive_int(vm_defaults.get(field), f"cluster.vm_defaults.{field}")
    for field in ("cpu_type", "bios", "machine", "clone_mode", "scsi_controller", "primary_disk"):
        require_non_empty_string(vm_defaults.get(field), f"cluster.vm_defaults.{field}")
    require(vm_defaults.get("pool") is None or isinstance(vm_defaults.get("pool"), str), "cluster.vm_defaults.pool must be null or a string")

    template_vmids: set[int] = set()
    template_names: set[str] = set()
    for template_name, template_value in templates.items():
        tctx = f"cluster.templates.{template_name}"
        template = as_mapping(template_value, tctx)
        vmid = template.get("vmid")
        require(isinstance(vmid, int), f"{tctx}: vmid must be an integer")
        vmid_int = cast(int, vmid)
        require(_in_range(vmid_int, reserved["templates"]), f"{tctx}: vmid must be within the declared template VMID range")
        require(vmid_int not in template_vmids, f"{tctx}: duplicate template VMID {vmid_int}")
        template_vmids.add(vmid_int)
        require(template.get("node") in nodes, f"{tctx}: node must reference a declared PVE node")

        for field in ("name", "storage_role", "source_storage_role", "cpu_type", "bios", "machine", "clone_mode", "scsi_controller", "primary_disk"):
            value = template.get(field)
            require(isinstance(value, str) and value, f"{tctx}: {field} must be a non-empty string")
        template_name_value = cast(str, template["name"])
        require(re.fullmatch(PVE_NAME_RE, template_name_value) is not None, f"{tctx}.name must be PVE-safe")
        require(template_name_value not in template_names, f"{tctx}: duplicate template name {template_name_value}")
        template_names.add(template_name_value)

        require_positive_int(template.get("disk_size_gib"), f"{tctx}.disk_size_gib")
        require_positive_int(template.get("primary_nics"), f"{tctx}.primary_nics")

        template_storage_role = cast(str, template["storage_role"])
        require(template_storage_role in storage_roles, f"{tctx}: storage_role must reference a declared storage role")
        template_storage = as_mapping(storage_roles[template_storage_role], f"cluster.storage_roles.{template_storage_role}")
        require("disk" in as_list(template_storage.get("content"), f"cluster.storage_roles.{template_storage_role}.content"), f"{tctx}: storage_role must point to storage with disk content")

        source_storage_role = cast(str, template["source_storage_role"])
        require(source_storage_role in storage_roles, f"{tctx}: source_storage_role must reference a declared storage role")

    pci_mappings = as_mapping(cluster_doc.get("pci_mappings"), "cluster.pci_mappings")
    for mapping_name, mapping_value in pci_mappings.items():
        mapping_context = f"cluster.pci_mappings.{mapping_name}"
        mapping = as_mapping(mapping_value, mapping_context)
        require_non_empty_string(mapping_name, f"{mapping_context}: mapping name")
        require_non_empty_string(mapping.get("type"), f"{mapping_context}.type")
        require(mapping.get("ha_allowed") is False, f"{mapping_context}.ha_allowed must be false for passthrough safety")
        mapping_defaults = as_mapping(mapping.get("defaults"), f"{mapping_context}.defaults")
        require_unknown_keys(mapping_defaults, {"pcie", "rombar", "xvga"}, f"{mapping_context}.defaults")
        for flag in ("pcie", "rombar", "xvga"):
            require(isinstance(mapping_defaults.get(flag), bool), f"{mapping_context}.defaults.{flag}: must be a boolean")
        mapping_nodes = as_mapping(mapping.get("nodes"), f"{mapping_context}.nodes")
        require(mapping_nodes, f"{mapping_context}.nodes must be a non-empty mapping")
        for node_name, node_mapping_value in mapping_nodes.items():
            require(node_name in nodes, f"{mapping_context}.nodes.{node_name}: node must reference a declared PVE node")
            node_mapping = as_mapping(node_mapping_value, f"{mapping_context}.nodes.{node_name}")
            require_non_empty_string(node_mapping.get("path"), f"{mapping_context}.nodes.{node_name}.path")
            require_positive_int(node_mapping.get("iommu_group"), f"{mapping_context}.nodes.{node_name}.iommu_group")

    return {
        "name": name,
        "default_template": default_template,
        "reserved_vm_id_ranges": reserved,
        "storage_roles": storage_roles,
        "automation": automation,
        "networks": networks,
        "nodes": nodes,
        "vm_defaults": vm_defaults,
        "templates": templates,
        "pci_mappings": pci_mappings,
    }
