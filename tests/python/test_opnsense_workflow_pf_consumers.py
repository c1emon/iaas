"""Focused loaded PF checks for gateway and interface-group consumers."""

from iaas.opnsense_workflow.pf_consumers import (
    check_gateway_active,
    check_interface_group_active,
)


UUID = "11111111-1111-4111-8111-111111111111"


def snapshot(rule: str | list[str]) -> dict:
    rules = rule if isinstance(rule, list) else [rule]
    return {"rules": {"filter rules": {item: {} for item in rules}, "nat rules": {}}}


def rule(*, interface: str = "igb0", route: str | None = "( igb0 192.0.2.1 )") -> str:
    option = f" route-to {route}" if route else ""
    return f'@4 pass in quick on {interface}{option} inet proto tcp from any to any label "{UUID}"'


def test_gateway_matches_native_uuid_route_to_physical_interface_and_next_hop() -> None:
    result = check_gateway_active(
        {"name": "WAN_GW", "interface": "wan", "physical_interfaces": ["igb0"], "gateway": "192.0.2.1"},
        snapshot(rule()),
        [{"resource": "filter-rules", "uuid": UUID, "gateway": "WAN_GW", "interface": ["wan"]}],
    )

    assert result["status"] == "verified"
    assert result["matches"][0]["route_to"] == ("igb0", "192.0.2.1")


def test_gateway_route_mismatch_fails_current_check() -> None:
    result = check_gateway_active(
        {"name": "WAN_GW", "interface": "wan", "physical_interfaces": ["igb0"], "gateway": "192.0.2.1"},
        snapshot(rule(route="( igb0 192.0.2.254 )")),
        [{"resource": "filter-rules", "uuid": UUID, "gateway": "WAN_GW", "interface": ["wan"]}],
    )

    assert result["status"] == "failed"


def test_interface_group_accepts_group_or_resolved_physical_member() -> None:
    result = check_interface_group_active(
        {"name": "External", "members": ["igb0", "igb1"]},
        snapshot([rule(interface="igb0"), rule(interface="igb1")]),
        [{"resource": "filter-rules", "uuid": UUID, "interface": ["External"]}],
    )

    assert result["status"] == "verified"


def test_interface_group_missing_physical_member_fails() -> None:
    result = check_interface_group_active(
        {"name": "External", "members": ["igb0", "igb1"]},
        snapshot(rule(interface="igb1")),
        [{"resource": "filter-rules", "uuid": UUID, "interface": ["External"]}],
    )

    assert result["status"] == "failed"
    assert result["reason"] == "loaded_interface_group_members_mismatch"


def test_no_enabled_consumer_is_not_applicable() -> None:
    result = check_interface_group_active(
        {"name": "External", "members": ["igb0"]},
        snapshot(rule(interface="igb0")),
        [{"resource": "filter-rules", "uuid": UUID, "interface": ["External"], "enabled": False}],
    )

    assert result["status"] == "not_applicable"


def test_one_to_one_nat_group_consumer_is_explicitly_unsupported() -> None:
    result = check_interface_group_active(
        {"name": "External", "members": ["igb0"]},
        snapshot(rule(interface="igb0")),
        [{"resource": "one-to-one-nat", "uuid": UUID, "interface": ["External"]}],
    )

    assert result["status"] == "unsupported"
    assert result["reason"] == "unsupported_nat_consumer_identity"


def test_consumer_without_uuid_cannot_be_inferred_from_description() -> None:
    result = check_gateway_active(
        {"name": "WAN_GW", "interface": "wan", "physical_interfaces": ["igb0"], "gateway": "192.0.2.1"},
        snapshot(rule()),
        [{"resource": "filter-rules", "gateway": "WAN_GW", "interface": ["wan"]}],
    )

    assert result["status"] == "incomplete"
    assert result["reason"] == "consumer_native_uuid_unavailable"


def test_gateway_requires_resolved_physical_interface_set() -> None:
    result = check_gateway_active(
        {"name": "WAN_GW", "interface": "wan", "gateway": "192.0.2.1"},
        snapshot(rule()),
        [{"resource": "filter-rules", "uuid": UUID, "gateway": "WAN_GW", "interface": ["wan"]}],
    )

    assert result["status"] == "incomplete"
    assert result["reason"] == "gateway_physical_interfaces_unavailable"
