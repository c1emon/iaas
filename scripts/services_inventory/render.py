"""Render service metadata into committed documentation."""

from __future__ import annotations

from typing import Any


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


def build_markdown(model: dict[str, Any]) -> str:
    """Render a compact Markdown service catalog."""
    lines = [
        "# Service Metadata Inventory",
        "",
        "Declared service metadata only: this document is generated offline from inventory/services.yml and cross-checked against inventory/vms.yml owner_vm names.",
        "",
        "It is not live verification and it does not create, update, or verify DNS, firewall, reverse proxy, PVE, guest, or network state.",
        "",
        "| Service | Owner VM | Endpoint | FQDN | Protocol | Port | Exposure | Auth | Review hints |",
        "|---|---|---|---|---|---:|---|---|---|",
    ]
    for service in model["services"]:
        for endpoint in service["endpoints"]:
            lines.append(
                f"| {service['name']} | {service['owner_vm']} | {_endpoint_label(endpoint)} | {endpoint['fqdn'] or '-'} | {endpoint['protocol']} | {endpoint['port']} | {endpoint['exposure']} | {endpoint['auth']} | {_hint_text(endpoint)} |"
            )

    if model["warnings"]:
        lines.extend(["", "## Warnings", "", "| Service | Endpoint | Code | Message |", "|---|---|---|---|"])
        for warning in model["warnings"]:
            lines.append(f"| {warning['service']} | {warning['endpoint']} | {warning['code']} | {warning['message']} |")

    return "\n".join(lines) + "\n"
