"""Render foundation recovery inventory into committed documentation.

The renderer is intentionally non-sensitive and offline-only: it formats the
validated inventory model into the checked-in recovery reference.
"""

from __future__ import annotations

from typing import Any

from iaas_automation.common.markdown import escape_table_cell


def _cell(value: Any) -> str:
    return escape_table_cell(value)


def _join(values: list[Any]) -> str:
    return ", ".join(str(value) for value in values) if values else "-"


def _health_summary(service: dict[str, Any]) -> str:
    """Condense a probe definition into a table-friendly description."""
    health = service.get("health_check")
    if not health:
        return "-"
    probe_type = health["type"]
    target = health["target"]
    summary = f"{probe_type} {target}"
    if health.get("expected_status"):
        summary += f" [{_join(health['expected_status'])}]"
    if health.get("record_type"):
        summary += f" ({str(health['record_type']).upper()})"
    if health.get("resolver"):
        summary += f" via {health['resolver']}"
    if health.get("expected_answer"):
        summary += f" -> {_join(health['expected_answer']) if isinstance(health['expected_answer'], list) else health['expected_answer']}"
    return summary


def _backup_summary(service: dict[str, Any]) -> str:
    """Summarize restore metadata without expanding into operational detail."""
    backup = service.get("backup_restore")
    if not backup:
        return "-"
    pieces = [backup["profile"], f"runbook: {backup['restore_runbook']}" ]
    if backup.get("backup_location"):
        pieces.append(f"location: {backup['backup_location']}")
    if backup.get("tested") is not None:
        pieces.append(f"tested: {str(backup['tested']).lower()}")
    return "; ".join(pieces)


def _break_glass_summary(service: dict[str, Any]) -> str:
    """Summarize operator access paths using reference strings only."""
    break_glass = service.get("break_glass")
    if not break_glass:
        return "-"
    pieces = [break_glass["method"], f"access: {break_glass['access_path']}"]
    if break_glass.get("secret_ref"):
        pieces.append(f"secret_ref: {break_glass['secret_ref']}")
    return "; ".join(pieces)


def build_markdown(model: dict[str, Any]) -> str:
    """Render a compact Markdown foundation recovery reference."""
    lines = [
        "# Foundation Recovery Reference",
        "",
        "Declared foundation recovery metadata only. This document is generated offline from the selected environment inventory/foundation.yml.",
        "",
        "Offline checks (`make foundation-check`) validate schema, references, restore order, storage facts, and generated-doc freshness without contacting internal infrastructure. `make foundation-health` is a separate explicit online read-only probe mode.",
        "",
        "## Minimum startup set",
        "",
    ]
    for index, service_name in enumerate(model["minimum_startup_set"], start=1):
        lines.append(f"{index}. {_cell(service_name)}")

    lines.extend([
        "",
        "## Recovery order",
        "",
    ])
    for index, service_name in enumerate(model["recovery_order"], start=1):
        lines.append(f"{index}. {_cell(service_name)}")

    lines.extend([
        "",
        "## Foundation hosts",
        "",
        "| Name | Kind | Management identity | Extra addresses | Accepted SPOF | Notes |",
        "|---|---|---|---|---|---|",
    ])
    for host in model["foundation_hosts"]:
        lines.append(
            f"| {_cell(host['name'])} | {_cell(host['kind'])} | {_cell(host['management_identity'])} | {_cell(_join(host.get('extra_addresses', [])))} | {_cell('yes' if host.get('accepted_spof') else 'no')} | {_cell(host.get('notes'))} |"
        )

    lines.extend([
        "",
        "## Foundation services",
        "",
        "| Service | Host | Runtime | Tier | Required before K3s | Restore order | External dependency | Dependencies | Health check | Backup / restore | Break-glass | Notes |",
        "|---|---|---|---|---|---:|---|---|---|---|---|---|",
    ])
    for service in model["foundation_services"]:
        lines.append(
            f"| {_cell(service['name'])} | {_cell(service.get('host') or '-')} | {_cell(service['runtime'])} | {_cell(service['tier'])} | {_cell('yes' if service['required_before_k3s'] else 'no')} | {_cell(service.get('restore_order') or '-')} | {_cell('yes' if service.get('external_dependency') else 'no')} | {_cell(_join(service.get('dependencies', [])))} | {_cell(_health_summary(service))} | {_cell(_backup_summary(service))} | {_cell(_break_glass_summary(service))} | {_cell(service.get('notes'))} |"
        )

    lines.extend([
        "",
        "## Dependencies",
        "",
        "| Service | Depends on |",
        "|---|---|",
    ])
    for service in model["foundation_services"]:
        lines.append(f"| {_cell(service['name'])} | {_cell(_join(service.get('dependencies', [])))} |")

    lines.extend([
        "",
        "## Health checks",
        "",
        "| Service | Probe | Expected |",
        "|---|---|---|",
    ])
    for service in model["foundation_services"]:
        health = service.get("health_check")
        if not health:
            lines.append(f"| {_cell(service['name'])} | - | - |")
            continue
        summary = _health_summary(service)
        expected = _join(health.get("expected_status", [])) if health.get("expected_status") else "-"
        lines.append(f"| {_cell(service['name'])} | {_cell(summary)} | {_cell(expected)} |")

    lines.extend([
        "",
        "## Backup / restore metadata",
        "",
        "| Service | Profile | Runbook | Location | Tested |",
        "|---|---|---|---|---|",
    ])
    for service in model["foundation_services"]:
        backup = service.get("backup_restore")
        if not backup:
            lines.append(f"| {_cell(service['name'])} | - | - | - | - |")
            continue
        lines.append(
            f"| {_cell(service['name'])} | {_cell(backup['profile'])} | {_cell(backup['restore_runbook'])} | {_cell(backup.get('backup_location'))} | {_cell(str(backup.get('tested')).lower() if backup.get('tested') is not None else '-') } |"
        )

    lines.extend([
        "",
        "## Break-glass metadata",
        "",
        "| Service | Method | Access path | Secret ref | Notes |",
        "|---|---|---|---|---|",
    ])
    for service in model["foundation_services"]:
        break_glass = service.get("break_glass")
        if not break_glass:
            lines.append(f"| {_cell(service['name'])} | - | - | - | - |")
            continue
        lines.append(
            f"| {_cell(service['name'])} | {_cell(break_glass['method'])} | {_cell(break_glass['access_path'])} | {_cell(break_glass.get('secret_ref'))} | {_cell(break_glass.get('notes'))} |"
        )

    legacy = model["schema_version"] == 1
    if model["storage_networks"]:
        endpoint_label = "TrueNAS endpoint" if legacy else "Endpoint"
        lines.extend([
            "", "## Storage-network facts", "",
            f"| Name | VLAN | Subnet | {endpoint_label} | Notes |",
            "|---|---:|---|---|---|",
        ])
        for network in model["storage_networks"]:
            endpoint = network["truenas_endpoint" if legacy else "endpoint"]
            lines.append(
                f"| {_cell(network['name'])} | {_cell(network['vlan_id'])} | {_cell(network['subnet'])} | {_cell(endpoint)} | {_cell(network.get('notes'))} |"
            )

    access = model["k3s_storage_access"]["phase_1"] if legacy else model.get("storage_access")
    if access is not None:
        title = "K3s storage access" if legacy else "Storage access"
        prefix = "Phase 1 " if legacy else ""
        lines.extend([
            "", f"### {title}", "",
            f"- {prefix}node classes: {_cell(_join(access['node_classes']))}",
            f"- {prefix}storage networks: {_cell(_join(access['storage_networks']))}",
        ])
        if access.get("notes"):
            lines.append(f"- Notes: {_cell(access['notes'])}")

    lines.extend([
        "",
        "## Warnings and known risks",
        "",
    ])
    if model["known_risks"]:
        for risk in model["known_risks"]:
            lines.append(f"- {_cell(risk['name'])}: {_cell(risk['message'])}")
    else:
        lines.append("- None recorded")

    return "\n".join(lines) + "\n"
