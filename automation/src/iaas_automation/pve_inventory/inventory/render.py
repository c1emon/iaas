"""Render validated inventory data into committed outputs."""

from __future__ import annotations

import copy
import json
from typing import Any

import yaml

from iaas_automation.common.errors import require


class IndentedSafeDumper(yaml.SafeDumper):
    """YAML dumper that indents sequences under mapping keys for yamllint."""

    def increase_indent(self, flow: bool = False, indentless: bool = False) -> Any:
        return super().increase_indent(flow, False)


def _ansible_connection_nic(vm: dict[str, Any]) -> dict[str, Any] | None:
    for nic in vm.get("nics", []):
        if nic.get("ansible_connection"):
            return nic
    return None


def _format_dns(dns: list[str]) -> str:
    return ", ".join(dns) if dns else "-"


def build_tfvars(model: dict[str, Any]) -> str:
    """Render the OpenTofu tfvars JSON payload."""
    payload = {
        "cluster": model["cluster"],
        "vms": model["vms"],
    }
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def build_ansible_inventory(model: dict[str, Any]) -> str:
    """Render the generated Ansible inventory."""
    groups: dict[str, dict[str, Any]] = {}
    for vm in model["vms"]:
        connection_nic = _ansible_connection_nic(vm)
        if connection_nic is None:
            continue
        hostvars = {
            "ansible_connection": "ssh",
            "ansible_host": connection_nic["ip_address"],
            "ansible_user": model["cluster"]["automation"]["ansible_user"],
            "ansible_become": False,
            "ansible_become_method": "sudo",
            "ansible_python_interpreter": "auto_silent",
            "pve_vmid": vm["vmid"],
            "pve_node": vm["node"],
            "pve_nics": copy.deepcopy(vm["nics"]),
            "pve_ansible_groups": vm["ansible_groups"],
            "pve_tags": vm["tags"],
            "pve_pool": vm["pool"],
            "pve_template": vm["template"]["name"],
            "pve_architecture": vm["template"]["architecture"],
            "pve_template_vmid": vm["template"]["vmid"],
            "pve_template_node": vm["template"]["node"],
            "pve_disk_storage_role": vm["storage"]["disk_role"],
            "pve_disk_datastore": vm["storage"]["disk_datastore_id"],
            "pve_started": vm["boot"]["started"],
            "pve_on_boot": vm["boot"]["on_boot"],
            "pve_cores": vm["resources"]["cores"],
            "pve_memory_mib": vm["resources"]["memory_mib"],
            "pve_root_disk_gib": vm["resources"]["root_disk_gib"],
        }
        groups.setdefault("pve_vms", {"hosts": {}})["hosts"][vm["name"]] = hostvars
        for group_name in vm["ansible_groups"]:
            groups.setdefault(group_name, {"hosts": {}})["hosts"][vm["name"]] = {}

    inventory = {"all": {"children": groups}}
    return yaml.dump(inventory, Dumper=IndentedSafeDumper, sort_keys=False, default_flow_style=False, explicit_start=True)


def build_markdown(model: dict[str, Any]) -> str:
    """Render a compact Markdown summary of declared VMs."""
    lines = ["# PVE VMs", "", "| Name | VMID | Lifecycle | Node | NIC | Network | MAC | IP | Gateway | Default route | Ansible conn | DNS | Template | Disk datastore | CPU | Memory | Disk | Started | On boot | Groups | Tags | Passthrough |", "|---|---:|---|---|---|---|---|---|---|---|---|---|---|---:|---:|---:|---|---|---|---|---|"]
    for vm in model["vms"]:
        if vm["passthrough"]:
            passthrough = "; ".join(
                f"{device['device']}:{device['mapping']} (pcie={'true' if device['pcie'] else 'false'}, rombar={'true' if device['rombar'] else 'false'}, xvga={'true' if device['xvga'] else 'false'})"
                for device in vm["passthrough"]
            )
        else:
            passthrough = "no"
        groups = ", ".join(vm["ansible_groups"])
        tags = ", ".join(vm["tags"])
        template = f"{vm['template']['name']} ({vm['template']['vmid']})"
        started = "yes" if vm["boot"]["started"] else "no"
        on_boot = "yes" if vm["boot"]["on_boot"] else "no"
        nics = vm["nics"] or [{}]
        for nic in nics:
            if nic:
                nic_name = f"{nic['name']} ({nic['role']})"
                network = f"{nic['network']['name']} / {nic['network']['bridge']}"
                mac_address = nic["mac_address"]
                ip_address = f"{nic['ip_address']}/{nic['prefix_length']}"
                gateway = nic["gateway"] or "-"
                default_route = "yes" if nic.get("default_route") else "no"
                ansible_connection = "yes" if nic.get("ansible_connection") else "no"
                dns = _format_dns(nic["dns"])
            else:
                nic_name = "-"
                network = "-"
                mac_address = "-"
                ip_address = "-"
                gateway = "-"
                default_route = "-"
                ansible_connection = "-"
                dns = "-"
            lines.append(
                f"| {vm['name']} | {vm['vmid']} | {vm['lifecycle_class']} | {vm['node']} | {nic_name} | {network} | {mac_address} | {ip_address} | {gateway} | {default_route} | {ansible_connection} | {dns} | {template} | {vm['storage']['disk_datastore_id']} | {vm['resources']['cores']} | {vm['resources']['memory_mib']} | {vm['resources']['root_disk_gib']} | {started} | {on_boot} | {groups} | {tags} | {passthrough} |"
            )
    lines.extend(["", "## Cluster defaults", "", f"- Default template: {model['cluster']['default_template']}", f"- VM cores: {model['cluster']['vm_defaults']['cores']}", f"- VM memory MiB: {model['cluster']['vm_defaults']['memory_mib']}", f"- VM root disk GiB: {model['cluster']['vm_defaults']['root_disk_gib']}"])
    return "\n".join(lines) + "\n"


def build_template_build_env(model: dict[str, Any]) -> str:
    """Render the generated Packer wrapper environment file."""
    template_build = model["cluster"]["automation"]["template_build"]
    def shell_quote(value: Any) -> str:
        text = str(value).replace("'", "'\\''")
        return f"'{text}'"

    values = {
        "TEMPLATE_VMID": template_build["template_vmid"],
        "TEMPLATE_NAME": template_build["template_name"],
        "IMAGE_URL": template_build["image_url"],
        "IMAGE_SHA512": template_build["image_sha512"],
        "IMAGE_URL_PREFIX": template_build["image_url_prefix"],
        "IMPORT_STORAGE": template_build["import_storage"],
        "DISK_STORAGE": template_build["disk_storage"],
        "BUILD_DOMAIN": template_build["build_domain"],
        "APT_MIRROR": template_build["apt_mirror"],
        "APT_SECURITY_MIRROR": template_build["apt_security_mirror"],
        "TIMEZONE": template_build["timezone"],
        "LOCALE": template_build["locale"],
        "CIUSER": template_build["ciuser"],
        "NAMESERVER": template_build["nameserver"],
        "BUILD_BRIDGE": template_build["build_bridge"],
    }
    lines = ["# Generated by iaas_automation.pve_inventory.cli; source from build-template.sh."]
    lines.extend(f"if [ -z \"${{{key}+x}}\" ]; then {key}={shell_quote(value)}; fi" for key, value in values.items())
    return "\n".join(lines) + "\n"


def render_outputs(model: dict[str, Any]) -> dict[str, str]:
    """Render all committed outputs and enforce no-secret content."""
    outputs = {
        "tfvars": build_tfvars(model),
        "ansible": build_ansible_inventory(model),
        "docs": build_markdown(model),
        "template_build_env": build_template_build_env(model),
    }
    for name, text in outputs.items():
        for forbidden in ("password_hash", "private_key", "token_secret", "api_token_secret"):
            require(forbidden not in text.lower(), f"{name}: generated output must not contain {forbidden}")
    return outputs
