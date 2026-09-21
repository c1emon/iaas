"""Offline checks for OPNsense origin and reference metadata."""

from copy import deepcopy

from iaas_automation.opnsense_workflow.classification import classify_resource, reference_support
from iaas_automation.opnsense_workflow.reader import COLLECTION_TARGETS, Reader


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
