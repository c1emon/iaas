"""Render service metadata into committed documentation."""

from __future__ import annotations

from typing import Any

from iaas_automation.common.markdown import escape_table_cell


def _hint_text(endpoint: dict[str, Any]) -> str:
    parts: list[str] = []
    if endpoint.get("dns_hint") is not None:
        parts.append(f"dns: {endpoint['dns_hint']}")
    if endpoint.get("reverse_proxy_hint") is not None:
        parts.append(f"reverse proxy: {endpoint['reverse_proxy_hint']}")
    if endpoint.get("opnsense_hint") is not None:
        parts.append(f"opnsense: {endpoint['opnsense_hint']}")
    return "; ".join(parts) if parts else "-"


def _endpoint_label(endpoint: dict[str, Any]) -> str:
    if endpoint.get("name"):
        return endpoint["name"]
    return "-"


def _escape_cell(value: Any) -> str:
    return escape_table_cell(value)


def build_markdown(model: dict[str, Any]) -> str:
    """Render a compact Markdown service catalog."""
    lines = [
        "# Service Metadata Inventory",
        "",
        "Declared service metadata only: this document is generated offline from the selected environment inventory/services.yml and cross-checked against the selected environment inventory/vms.yml owner_vm names.",
        "",
        "It is not live verification and it does not create, update, or verify DNS, firewall, reverse proxy, PVE, guest, or network state.",
        "",
        "| Service | Owner VM | Endpoint | FQDN | Protocol | Port | Exposure | Auth | Review hints |",
        "|---|---|---|---|---|---:|---|---|---|",
    ]
    for service in model["services"]:
        for endpoint in service["endpoints"]:
            lines.append(
                f"| {_escape_cell(service['name'])} | {_escape_cell(service['owner_vm'])} | {_escape_cell(_endpoint_label(endpoint))} | {_escape_cell(endpoint['fqdn'] or '-')} | {_escape_cell(endpoint['protocol'])} | {_escape_cell(endpoint['port'])} | {_escape_cell(endpoint['exposure'])} | {_escape_cell(endpoint['auth'])} | {_escape_cell(_hint_text(endpoint))} |"
            )

    if model["warnings"]:
        lines.extend(["", "## Warnings", "", "| Service | Endpoint | Code | Message |", "|---|---|---|---|"])
        for warning in model["warnings"]:
            lines.append(
                f"| {_escape_cell(warning['service'])} | {_escape_cell(warning['endpoint'])} | {_escape_cell(warning['code'])} | {_escape_cell(warning['message'])} |"
            )

    return "\n".join(lines) + "\n"
