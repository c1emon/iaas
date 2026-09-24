"""Model assembly for validated foundation recovery data.

This layer adds derived lookup tables and recovery-order summaries for the
renderer and live health checker.
"""

from __future__ import annotations

from typing import Any


def build_model(inventory: dict[str, Any]) -> dict[str, Any]:
    """Combine validated foundation data into the renderer/health model."""
    services = list(inventory["foundation_services"])
    ordered_required = sorted((service for service in services if service["required_before_k3s"]), key=lambda service: service["restore_order"])
    known_risks: list[dict[str, str]] = []
    for host in inventory["foundation_hosts"]:
        if host.get("accepted_spof"):
            known_risks.append({"kind": "host", "name": host["name"], "message": "accepted single point of failure"})
    for service in services:
        for risk in service.get("known_risks", []):
            known_risks.append({"kind": "service", "name": service["name"], "message": risk})

    return {
        **inventory,
        "hosts_by_name": {host["name"]: host for host in inventory["foundation_hosts"]},
        "services_by_name": {service["name"]: service for service in services},
        "minimum_startup_set": [service["name"] for service in ordered_required],
        "recovery_order": [service["name"] for service in ordered_required],
        "known_risks": known_risks,
    }
