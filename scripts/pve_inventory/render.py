"""Render validated inventory data into committed outputs."""

from __future__ import annotations

import json
from typing import Any

import yaml

from .errors import require


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
        hostvars = {
            "ansible_connection": "ssh",
            "ansible_host": vm["ip_address"],
            "ansible_user": model["cluster"]["automation"]["ansible_user"],
            "ansible_become": True,
            "ansible_become_method": "sudo",
            "ansible_python_interpreter": "{{ ansible_playbook_python }}",
            "pve_vmid": vm["vmid"],
            "pve_node": vm["node"],
            "pve_network": vm["network"]["name"],
            "pve_bridge": vm["network"]["bridge"],
            "pve_gateway": vm["gateway"],
            "pve_dns": vm["dns"],
            "pve_tags": vm["tags"],
            "pve_pool": vm["pool"],
            "pve_template": vm["template"]["name"],
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
    return yaml.safe_dump(inventory, sort_keys=False, default_flow_style=False)


def build_markdown(model: dict[str, Any]) -> str:
    """Render a compact Markdown summary of declared VMs."""
    lines = ["# PVE VMs", "", "| Name | VMID | Lifecycle | Node | Network | IP | Template | Disk datastore | CPU | Memory | Disk | Started | On boot | Groups | Tags | Passthrough |", "|---|---:|---|---|---|---|---|---|---:|---:|---:|---|---|---|---|---|"]
    for vm in model["vms"]:
        passthrough = "yes" if vm["passthrough"] else "no"
        groups = ", ".join(vm["ansible_groups"])
        tags = ", ".join(vm["tags"])
        template = f"{vm['template']['name']} ({vm['template']['vmid']})"
        started = "yes" if vm["boot"]["started"] else "no"
        on_boot = "yes" if vm["boot"]["on_boot"] else "no"
        lines.append(
            f"| {vm['name']} | {vm['vmid']} | {vm['lifecycle_class']} | {vm['node']} | {vm['network']['name']} | {vm['ip_address']}/{vm['prefix_length']} | {template} | {vm['storage']['disk_datastore_id']} | {vm['resources']['cores']} | {vm['resources']['memory_mib']} | {vm['resources']['root_disk_gib']} | {started} | {on_boot} | {groups} | {tags} | {passthrough} |"
        )
    lines.extend(["", "## Cluster defaults", "", f"- Default template: {model['cluster']['default_template']}", f"- VM cores: {model['cluster']['vm_defaults']['cores']}", f"- VM memory MiB: {model['cluster']['vm_defaults']['memory_mib']}", f"- VM root disk GiB: {model['cluster']['vm_defaults']['root_disk_gib']}"])
    return "\n".join(lines) + "\n"


def render_outputs(model: dict[str, Any]) -> dict[str, str]:
    """Render all committed outputs and enforce no-secret content."""
    outputs = {
        "tfvars": build_tfvars(model),
        "ansible": build_ansible_inventory(model),
        "docs": build_markdown(model),
    }
    for name, text in outputs.items():
        for forbidden in ("password_hash", "private_key", "token_secret", "api_token_secret"):
            require(forbidden not in text.lower(), f"{name}: generated output must not contain {forbidden}")
    return outputs
