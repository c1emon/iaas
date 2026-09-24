"""Offline checks for OPNsense origin and reference metadata."""

from copy import deepcopy

import pytest

from iaas.opnsense_workflow.classification import classify_resource, reference_support
from iaas.opnsense_workflow.reader import COLLECTION_TARGETS, Reader


TARGET = {"host": "firewall", "endpoint": "https://firewall.example", "ssl_verify": True}
CREDENTIALS = {"OPNSENSE_API_KEY": "key", "OPNSENSE_API_SECRET": "secret"}


def _alias(name="NETS", alias_type="host", content=None):
    return {
        "name": name,
        "type": alias_type,
        "content": content if content is not None else ["192.0.2.10"],
        "description": "fixture",
        "enabled": True,
    }


def test_internal_alias_is_system_read_only_and_supports_literal_address_reference():
    row = _alias("__lan_network", "internal", ["192.0.2.0/24"])
    classification, nature = classify_resource("aliases", row, identity=[row["name"]], configuration=None)

    assert classification == {
        "origin": "system_builtin",
        "management": "read_only",
        "basis": ["native_internal_type", "persistent_configuration"],
    }
    assert nature == ["persistent_configuration"]
    assert reference_support("aliases", row, classification) == {
        "label": "aliases:__lan_network",
        "roles": ["address"],
        "basis": ["native_internal_type", "reference_role_from_content", "complete_literal_membership"],
        "dependencies_complete": True,
        "ip_protocol": "inet",
    }


@pytest.mark.parametrize("name, description, expire", [
    ("bogons", "bogon networks (internal)", ""),
    ("bogonsv6", "bogon networks IPv6 (internal)", ""),
    ("virusprot", "overload table for rate limiting (internal)", "3600"),
    ("sshlockout", "abuse lockout table (internal)", "3600"),
])
def test_fixed_static_external_alias_requires_exact_native_payload(name, description, expire):
    native = {
        "uuid": name, "name": name,
        "type": {"external": {"selected": 1}, "host": {"selected": 0}},
        "description": description,
        "expire": expire, "content": "", "enabled": "1",
    }
    normalized = {
        "name": name, "type": "external", "description": description,
        "content": [], "enabled": True,
    }
    classified, _ = classify_resource(
        "aliases", normalized, identity=[name], configuration=None, native_row=native,
    )
    assert classified["origin"] == "system_builtin"
    assert classified["management"] == "read_only"
    assert classified["basis"] == ["native_static_child", "persistent_configuration"]


def test_static_alias_name_with_user_uuid_remains_user_external():
    native = {
        "uuid": "550e8400-e29b-41d4-a716-446655440000", "name": "bogons",
        "type": "external", "description": "bogon networks (internal)",
        "expire": "", "content": "", "enabled": "1",
    }
    row = {"name": "bogons", "type": "external", "content": [], "enabled": True}
    classified, _ = classify_resource(
        "aliases", row, identity=["bogons"], configuration=None, native_row=native,
    )
    assert classified["origin"] == "user_config"
    assert classified["management"] == "independent"


def test_static_alias_uuid_with_conflicting_payload_stays_unknown():
    native = {
        "uuid": "bogons", "name": "bogons", "type": "external",
        "description": "user supplied", "expire": "", "content": "", "enabled": "1",
    }
    row = {"name": "bogons", "type": "external", "content": [], "enabled": True}
    classified, _ = classify_resource(
        "aliases", row, identity=["bogons"], configuration=None, native_row=native,
    )
    assert classified["origin"] == "unknown"
    assert classified["management"] == "unknown"


def test_external_and_dynamic_aliases_remain_user_managed():
    external, _ = classify_resource("aliases", _alias(alias_type="external"), identity=["NETS"], configuration=None)
    dynamic, nature = classify_resource(
        "aliases", _alias(alias_type="urltable", content=["https://example.test/list"]),
        identity=["NETS"], configuration=None,
    )

    assert external["origin"] == "user_config"
    assert external["management"] == "independent"
    assert "native_external_type" in external["basis"]
    assert dynamic["origin"] == "user_config"
    assert dynamic["management"] == "independent"
    assert nature == ["persistent_configuration", "dynamic_contents"]


def test_conflicting_origin_marker_fails_closed():
    row = _alias(alias_type="internal") | {"origin": "user_config"}
    classified, _ = classify_resource("aliases", row, identity=["NETS"], configuration=None)
    assert classified["origin"] == "unknown"
    assert classified["management"] == "unknown"
    assert classified["reason"] == "conflicting_classification"


def test_group_and_unmarked_gateway_do_not_gain_system_or_read_only_status():
    group, _ = classify_resource(
        "interface-groups", {"name": "wireguard", "members": []}, identity=["wireguard"], configuration=None,
    )
    gateway, _ = classify_resource(
        "gateways", {"name": "WAN", "gateway": "", "uuid": "native"},
        identity=["native:native"], configuration=None,
    )

    assert group["origin"] == group["management"] == "unknown"
    assert gateway["origin"] == "unknown"
    assert gateway["management"] == "unknown"
    assert gateway["reason"] == "classification_evidence_missing"


def test_fixed_static_group_needs_all_native_static_fields():
    row = {
        "name": "wireguard", "ifname": "wireguard", "uuid": "wireguard", "sequence": 10,
        "description": "WireGuard (Group)", "members": [],
    }
    classified, _ = classify_resource(
        "interface-groups", row, identity=["wireguard"], configuration=None,
        native_row=row,
    )
    assert classified["origin"] == "derived"
    assert classified["management"] == "read_only"
    assert reference_support("interface-groups", row, classified) == {
        "label": "interface-groups:wireguard",
        "roles": ["interface-group"],
        "basis": ["native_static_child", "reference_role_from_native_identity"],
        "dependencies_complete": True,
    }


def test_static_group_uuid_mismatch_is_not_treated_as_derived():
    row = {
        "name": "wireguard", "ifname": "wireguard", "uuid": "user-created",
        "sequence": 10, "description": "WireGuard (Group)", "members": [],
    }
    classified, _ = classify_resource(
        "interface-groups", row, identity=["wireguard"], configuration=None,
        native_row=row,
    )
    assert classified["origin"] == "unknown"
    assert classified["management"] == "unknown"
    assert reference_support("interface-groups", row, classified) is None


def test_static_group_accepts_unselected_native_member_choices_after_conversion():
    native = {
        "name": "wireguard", "ifname": "wireguard", "uuid": "wireguard",
        "sequence": "10", "descr": "WireGuard (Group)",
        "members": {"wg0": {"selected": 0}, "wg1": {"selected": 0}},
    }
    normalized = {
        "name": "wireguard", "uuid": "wireguard", "sequence": 10,
        "description": "WireGuard (Group)", "members": [],
    }
    classified, _ = classify_resource(
        "interface-groups", normalized, identity=["wireguard"], configuration=None,
        native_row=native,
    )
    assert classified["origin"] == "derived"
    assert classified["management"] == "read_only"


def test_gui_group_false_does_not_remove_normal_group_crud_evidence():
    row = {"name": "vpn_users", "members": ["tun0"], "gui_group": False}
    classified, _ = classify_resource(
        "interface-groups", row, identity=["vpn_users"], configuration=None,
    )
    assert classified["origin"] == "user_config"
    assert classified["management"] == "independent"


def test_conversion_failure_does_not_erase_editable_model_classification():
    row = _alias("external_list", "external", ["opaque-provider-value"])
    classified, _ = classify_resource(
        "aliases", row, identity=["external_list"], configuration=None,
    )
    assert classified["origin"] == "user_config"
    assert classified["management"] == "independent"
    assert "native_external_type" in classified["basis"]


def test_preconfigured_editable_rule_stays_ordinary_configuration():
    row = {"description": "default allow", "uuid": "rule-1", "enabled": True}
    classified, _ = classify_resource(
        "filter-rules", row, identity=["native:rule-1"], configuration=None,
    )
    assert classified["origin"] == "user_config"
    assert classified["management"] == "independent"


def test_invalid_native_selector_is_incomplete_without_a_false_alias_classification():
    class Transport:
        def list(self, target, **kwargs):
            return [_alias("BROKEN", "host", ["192.0.2.1"]) | {
                "type": {"host": {"selected": 1}, "network": {"selected": 1}},
            }]

        def interfaces(self):
            return []

    observation = Reader(TARGET, CREDENTIALS, Transport()).read(["aliases"])["aliases"]
    assert observation["status"] == "incomplete"
    assert observation["objects"] == []
    assert observation["reason"] == ["malformed_native_selector"]


def test_reader_marks_configuration_scope_and_keeps_system_reference_metadata():
    class Transport:
        def list(self, target, **kwargs):
            assert target == COLLECTION_TARGETS["aliases"]
            return [_alias("__lan_network", "internal", ["192.0.2.0/24"]), _alias()]

        def interfaces(self):
            return ["lan"]

    observation = Reader(TARGET, CREDENTIALS, Transport()).read(["aliases"])["aliases"]
    assert observation["status"] == "complete"
    assert observation["observation_scope"] == "configuration"
    assert observation["enumeration_source"].startswith("oxlorg.opnsense@26.1.11:")
    system, user = observation["objects"]
    assert system["classification"]["origin"] == "system_builtin"
    assert system["reference_support"]["roles"] == ["address"]
    assert user["classification"]["origin"] == "user_config"
    assert "reference_support" not in user
