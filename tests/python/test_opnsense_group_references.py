from __future__ import annotations

from typing import Any

import pytest

from iaas_automation.common.errors import ValidationError
from iaas_automation.opnsense_validation import validate_documents


def _group(*, name: str = "Internal", state: str = "present", members: list[str] | None = None) -> dict[str, Any]:
    if state == "absent":
        return {"name": name, "state": state}
    return {
        "name": name,
        "state": state,
        "members": members if members is not None else ["lan"],
        "gui_group": True,
        "sequence": 0,
    }


def _filter_rule(*, interface: str = "Internal", action: str = "pass", destination_net: str = "any",
                 destination_invert: bool = False) -> dict[str, Any]:
    return {
        "scope": "edge",
        "slug": "web",
        "state": "present",
        "enabled": True,
        "sequence": 100,
        "interface": [interface],
        "direction": "in",
        "action": action,
        "quick": True,
        "ip_protocol": "inet",
        "protocol": "TCP",
        "source_net": "any",
        "destination_net": destination_net,
        "destination_invert": destination_invert,
    }


def _dnat_rule(interface: str = "Internal") -> dict[str, Any]:
    return {
        "scope": "edge",
        "slug": "web",
        "state": "present",
        "enabled": True,
        "sequence": 100,
        "interface": [interface],
        "ip_protocol": "inet",
        "protocol": "TCP",
        "source_net": "any",
        "destination_net": "wanip",
        "target": "192.0.2.10",
        "nat_reflection": "",
        "associated_rule": "",
    }


def _one_to_one_rule(interface: str = "Internal") -> dict[str, Any]:
    return {
        "scope": "edge",
        "slug": "mail",
        "state": "present",
        "enabled": True,
        "sequence": 10,
        "interface": interface,
        "type": "nat",
        "external": "198.51.100.10",
        "source_net": "192.0.2.10",
        "destination_net": "any",
        "nat_reflection": "disable",
    }


def _context(*, interface: str = "Internal") -> dict[str, Any]:
    return {
        "interface_networks": {interface: ["192.0.2.0/24"]},
        "aliases": [],
    }


def test_mixed_case_group_reference_preserves_case_without_weakening_filter_guards() -> None:
    documents = {
        "interface-groups": {"opnsense_interface_groups": [_group()]},
        "filter-rules": {
            "opnsense_filter_rules": [_filter_rule()],
            "opnsense_filter_rule_context": _context(),
        },
    }

    validate_documents(documents)

    denied = documents["filter-rules"]["opnsense_filter_rules"][0].copy()
    denied.update(action="block", destination_net="Internal")
    with pytest.raises(ValidationError, match="deny rule must not include"):
        validate_documents({
            "interface-groups": {"opnsense_interface_groups": [_group()]},
            "filter-rules": {
                "opnsense_filter_rules": [denied],
                "opnsense_filter_rule_context": _context(),
            },
        })


def test_group_inversion_guard_remains_in_force_for_mixed_case_reference() -> None:
    with pytest.raises(ValidationError, match="deny rule must not include"):
        validate_documents({
            "interface-groups": {"opnsense_interface_groups": [_group()]},
            "filter-rules": {
                "opnsense_filter_rules": [_filter_rule(
                    action="block", destination_net="External", destination_invert=True,
                )],
                "opnsense_filter_rule_context": _context(),
            },
        })


@pytest.mark.parametrize(
    ("resource", "document"),
    [
        ("filter-rules", {
            "opnsense_filter_rules": [_filter_rule()],
        }),
        ("dnat", {"opnsense_dnat_rules": [_dnat_rule()]}),
        ("one-to-one-nat", {"opnsense_one_to_one_nat_rules": [_one_to_one_rule()]}),
    ],
)
def test_selected_absent_group_cannot_be_referenced_by_surviving_records(resource: str,
                                                                            document: dict[str, Any]) -> None:
    with pytest.raises(ValidationError, match="references an interface group selected for deletion"):
        validate_documents({
            "interface-groups": {"opnsense_interface_groups": [_group(state="absent")]},
            resource: document,
        })


def test_selected_nested_group_is_rejected() -> None:
    with pytest.raises(ValidationError, match="nested interface groups are not supported"):
        validate_documents({
            "interface-groups": {
                "opnsense_interface_groups": [
                    _group(name="Parent", members=["Child"]),
                    _group(name="Child"),
                ],
            },
        })


def test_legal_external_group_reference_is_allowed() -> None:
    validate_documents({
        "filter-rules": {
            "opnsense_filter_rules": [_filter_rule(interface="External")],
            "opnsense_filter_rule_context": _context(interface="External"),
        },
    })


@pytest.mark.parametrize(
    ("resource", "document"),
    [
        ("vips", {"opnsense_vips": [{
            "description": "public",
            "interface": "Internal",
            "address": "198.51.100.10/32",
            "bind": True,
            "expand": False,
            "state": "present",
        }]}),
        ("gateways", {"opnsense_gateways": [{
            "name": "HOLE",
            "interface": "Internal",
            "ip_protocol": "inet",
            "gateway": "198.19.0.253",
            "default_gw": False,
            "far_gw": False,
            "monitor_disable": False,
            "monitor_noroute": False,
            "monitor": "198.19.0.253",
            "force_down": False,
            "latency_low": 200,
            "latency_high": 500,
            "loss_low": 10,
            "loss_high": 20,
            "interval": 1,
            "time_period": 60,
            "loss_interval": 4,
            "data_length": 1,
            "priority": 255,
            "weight": 1,
            "description": "gateway",
            "state": "present",
        }]}),
    ],
)
def test_uppercase_group_name_remains_invalid_for_vip_and_gateway(resource: str,
                                                                    document: dict[str, Any]) -> None:
    with pytest.raises(ValidationError, match="interface: has invalid syntax"):
        validate_documents({resource: document})
