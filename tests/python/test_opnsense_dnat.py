from __future__ import annotations

from copy import deepcopy
from typing import Any

import pytest

from iaas_automation.common.errors import ValidationError
from iaas_automation.opnsense_validation.dnat import validate_dnat


def _present(**overrides: Any) -> dict[str, Any]:
    record: dict[str, Any] = {
        "scope": "edge",
        "slug": "web",
        "state": "present",
        "enabled": True,
        "sequence": 100,
        "interface": ["wan"],
        "ip_protocol": "inet",
        "protocol": "TCP",
        "source_net": "any",
        "destination_net": "wanip",
        "target": "192.0.2.10",
        "nat_reflection": "",
        "associated_rule": "",
    }
    record.update(overrides)
    return record


def test_valid_present_returns_stable_identity() -> None:
    record = _present(
        source_port="1024-2048",
        destination_port="https",
        local_port="8443",
        source_invert=False,
        destination_invert=False,
        log=False,
        pool_opts="round-robin",
        tag="dnat",
        tagged="incoming",
        associated_rule="rule",
    )

    assert validate_dnat(record, "opnsense_dnat_rules[0]") == ("iaas:opnsense:dnat:edge:web",)


def test_absent_requires_only_identity_and_state() -> None:
    assert validate_dnat(
        {"scope": "edge", "slug": "web", "state": "absent"}, "opnsense_dnat_rules[0]"
    ) == ("iaas:opnsense:dnat:edge:web",)


def test_absent_rejects_present_only_fields() -> None:
    with pytest.raises(ValidationError, match="unknown keys enabled"):
        validate_dnat(
            {"scope": "edge", "slug": "web", "state": "absent", "enabled": False},
            "opnsense_dnat_rules[0]",
        )


@pytest.mark.parametrize("field", [
    "enabled", "sequence", "interface", "ip_protocol", "protocol", "source_net",
    "destination_net", "target", "nat_reflection", "associated_rule",
])
def test_present_requires_complete_managed_shape(field: str) -> None:
    record = _present()
    del record[field]
    with pytest.raises(ValidationError, match=f"missing required keys {field}"):
        validate_dnat(record, "opnsense_dnat_rules[0]")


def test_unknown_provider_or_identity_overrides_fail() -> None:
    for field in ("description", "uuid", "match_fields", "no_port_forward", "unexpected"):
        record = _present(**{field: "value"})
        with pytest.raises(ValidationError, match=f"unknown keys {field}"):
            validate_dnat(record, "opnsense_dnat_rules[0]")


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("enabled", "true"),
        ("sequence", True),
        ("interface", "wan"),
        ("ip_protocol", "inet4"),
        ("source_invert", 1),
        ("nat_reflection", None),
        ("associated_rule", False),
    ],
)
def test_strict_primitives_and_enums_fail(field: str, value: Any) -> None:
    record = _present(**{field: value})
    with pytest.raises(ValidationError):
        validate_dnat(record, "opnsense_dnat_rules[0]")


def test_unknown_protocol_fails_closed() -> None:
    with pytest.raises(ValidationError, match="protocol exposed"):
        validate_dnat(_present(protocol="bogus"), "opnsense_dnat_rules[0]")


def test_sequence_and_interface_boundaries() -> None:
    validate_dnat(_present(sequence=1, interface=["opt1", "pppoe0"]), "opnsense_dnat_rules[0]")
    validate_dnat(_present(interface=["Internal"]), "opnsense_dnat_rules[0]")
    validate_dnat(_present(sequence=999999), "opnsense_dnat_rules[0]")
    for record in (_present(sequence=0), _present(sequence=1000000), _present(interface=[]), _present(interface=["lo0"])):
        with pytest.raises(ValidationError):
            validate_dnat(record, "opnsense_dnat_rules[0]")


def test_source_and_destination_ranges_are_valid_but_local_range_is_not() -> None:
    validate_dnat(
        _present(source_port="1000-2000", destination_port="443", local_port="8443"),
        "opnsense_dnat_rules[0]",
    )
    with pytest.raises(ValidationError, match="local_port"):
        validate_dnat(_present(local_port="8000-8010"), "opnsense_dnat_rules[0]")
    with pytest.raises(ValidationError, match="local_port"):
        validate_dnat(_present(local_port="any"), "opnsense_dnat_rules[0]")


def test_ports_require_transport_protocol() -> None:
    with pytest.raises(ValidationError, match="ports require"):
        validate_dnat(_present(protocol="ICMP", destination_port="8"), "opnsense_dnat_rules[0]")


@pytest.mark.parametrize(
    ("ip_protocol", "field", "value"),
    [("inet", "target", "2001:db8::10"), ("inet6", "destination_net", "192.0.2.1")],
)
def test_literal_address_family_conflicts_fail(ip_protocol: str, field: str, value: str) -> None:
    with pytest.raises(ValidationError, match="address family"):
        validate_dnat(_present(ip_protocol=ip_protocol, **{field: value}), "opnsense_dnat_rules[0]")


@pytest.mark.parametrize("target", ["any", "(self)", "192.0.2.0/24", "999.1.1.1"])
def test_target_must_be_an_address_or_alias(target: str) -> None:
    with pytest.raises(ValidationError, match="IP/CIDR"):
        validate_dnat(_present(target=target), "opnsense_dnat_rules[0]")


def test_empty_optional_values_are_valid_clear_values() -> None:
    record = _present(source_port="", destination_port="", local_port="", tag="", tagged="")
    validate_dnat(record, "opnsense_dnat_rules[0]")


@pytest.mark.parametrize("field", ["tag", "tagged"])
def test_native_strict_text_rejects_whitespace_and_control_characters(field: str) -> None:
    with pytest.raises(ValidationError, match="control characters"):
        validate_dnat(_present(**{field: "invalid value"}), "opnsense_dnat_rules[0]")


def test_input_is_not_mutated() -> None:
    record = _present()
    original = deepcopy(record)
    validate_dnat(record, "opnsense_dnat_rules[0]")
    assert record == original
