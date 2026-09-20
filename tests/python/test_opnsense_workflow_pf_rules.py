"""Focused checks for loaded OPNsense 26.7.3 port-alias PF rules."""

from copy import deepcopy

import pytest

from iaas_automation.opnsense_workflow.pf_rules import check_port_alias_active


UUID = "11111111-1111-4111-8111-111111111111"
ALIAS = {"name": "WEB_PORTS", "type": "port", "content": ["80", "443", "8000-8002"]}
CONSUMER = {
    "uuid": UUID,
    "protocol": "tcp",
    "source_port": ["any"],
    "destination_port": ["WEB_PORTS"],
}


def snapshot(rule: str | list[str], *, nat: dict[str, dict] | None = None) -> dict:
    rules = rule if isinstance(rule, list) else [rule]
    return {"rules": {"filter rules": {item: {"evaluations": 3} for item in rules}, "nat rules": nat or {}}}


def loaded_rule(
    destination_port: str = "{ 80 443 8000:8002 }",
    *,
    protocol: str = "tcp",
    source_port: str | None = None,
    label: str = UUID,
) -> str:
    source = "any" if source_port is None else f"any port {source_port}"
    return (
        f'@42 pass in quick on wan inet proto {protocol} '
        f'from {source} to any port {destination_port} label "{label}"'
    )


def test_expanded_destination_alias_matches_protocol_and_range() -> None:
    result = check_port_alias_active(ALIAS, snapshot(loaded_rule()), [CONSUMER])

    assert result["status"] == "verified"
    assert result["matches"][0]["pf_index"] == 42
    assert result["matches"][0]["destination_port"] == "{ 80 443 8000:8002 }"


def test_source_and_destination_roles_are_not_interchangeable() -> None:
    consumer = deepcopy(CONSUMER)
    consumer["source_port"] = ["WEB_PORTS"]
    consumer["destination_port"] = ["any"]

    result = check_port_alias_active(ALIAS, snapshot(loaded_rule()), [consumer])

    assert result["status"] == "failed"
    assert result["reason"] == "loaded_port_alias_rule_mismatch"


@pytest.mark.parametrize(
    "rule_port",
    ["{ 80 443 8000:8002 }", "{ 443 80 8002 8000:8001 }"],
)
def test_overlapping_and_split_ranges_have_equal_port_semantics(rule_port: str) -> None:
    result = check_port_alias_active(ALIAS, snapshot(loaded_rule(rule_port)), [CONSUMER])

    assert result["status"] == "verified"


def test_same_uuid_split_pf_rows_are_aggregated_before_comparison() -> None:
    result = check_port_alias_active(
        ALIAS,
        snapshot([loaded_rule("{ 80 }"), loaded_rule("{ 443 8000:8002 }")]),
        [CONSUMER],
    )

    assert result["status"] == "verified"


def test_unexpanded_alias_macro_cannot_verify_loaded_members() -> None:
    result = check_port_alias_active(
        ALIAS,
        snapshot(loaded_rule("$WEB_PORTS")),
        [CONSUMER],
    )

    assert result["status"] in {"unknown", "incomplete"}


def test_native_uuid_is_the_only_rule_correlation() -> None:
    rule = loaded_rule(label="22222222-2222-4222-8222-222222222222")

    result = check_port_alias_active(ALIAS, snapshot(rule), [CONSUMER])

    assert result["status"] == "failed"
    assert result["reason"] == "consumer_native_uuid_not_loaded"


def test_complete_configuration_without_consumer_is_not_applicable() -> None:
    result = check_port_alias_active(ALIAS, snapshot(loaded_rule()), [])

    assert result == {
        "status": "not_applicable",
        "reason": "complete_consumer_configuration_empty",
    }


@pytest.mark.parametrize(
    "bad_snapshot",
    [
        {},
        {"rules": {"filter rules": {}, "nat rules": []}},
        {"status": "failed", "rules": {"filter rules": {}, "nat rules": {}}},
    ],
)
def test_snapshot_failure_or_truncation_cannot_become_empty_success(bad_snapshot: dict) -> None:
    result = check_port_alias_active(ALIAS, bad_snapshot, [])

    assert result["status"] == "incomplete"
    assert result["reason"] != "complete_consumer_configuration_empty"


def test_malformed_port_rule_is_incomplete_when_uuid_is_related() -> None:
    malformed = loaded_rule("{ 80 443")
    result = check_port_alias_active(ALIAS, snapshot(malformed), [CONSUMER])

    assert result["status"] == "incomplete"


def test_nat_rule_without_native_uuid_cannot_verify_consumer() -> None:
    rule = loaded_rule()
    result = check_port_alias_active(
        ALIAS,
        {"rules": {"filter rules": {}, "nat rules": {rule: {"evaluations": 1}}}},
        [CONSUMER | {"resource": "dnat"}],
    )

    assert result["status"] == "incomplete"
    assert result["reason"] == "unsupported_nat_consumer_identity"


def test_dnat_local_port_alias_is_unsupported_rdr_target_not_not_applicable() -> None:
    consumer = {
        "uuid": UUID,
        "protocol": "tcp",
        "destination_port": ["any"],
        "local_port": ["WEB_PORTS"],
    }

    result = check_port_alias_active(ALIAS, snapshot(loaded_rule()), [consumer])

    assert result["status"] == "incomplete"
    assert result["reason"] == "unsupported_consumer_translated_port_role"


def test_disabled_or_not_enabled_consumer_is_not_applicable() -> None:
    disabled = CONSUMER | {"disabled": True}
    disabled_result = check_port_alias_active(ALIAS, snapshot(loaded_rule()), [disabled])
    assert disabled_result["status"] == "not_applicable"

    disabled = CONSUMER | {"enabled": False}
    disabled_result = check_port_alias_active(ALIAS, snapshot(loaded_rule()), [disabled])
    assert disabled_result["status"] == "not_applicable"


def test_malformed_consumer_enabled_state_is_incomplete() -> None:
    result = check_port_alias_active(
        ALIAS,
        snapshot(loaded_rule()),
        [CONSUMER | {"enabled": "false"}],
    )

    assert result["status"] == "incomplete"
