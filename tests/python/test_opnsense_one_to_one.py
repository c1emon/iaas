from copy import deepcopy

import pytest

from iaas.common.errors import ValidationError
from iaas.opnsense_validation.one_to_one import validate_one_to_one


def valid_record(**changes):
    record = {
        "scope": "edge",
        "slug": "mail",
        "state": "present",
        "enabled": True,
        "sequence": 10,
        "interface": "wan",
        "type": "binat",
        "external": "198.51.100.0/24",
        "source_net": "192.0.2.0/24",
        "destination_net": "any",
        "nat_reflection": "disable",
        "source_invert": False,
        "destination_invert": False,
        "log": False,
    }
    record.update(changes)
    return record


def test_equal_sized_binat_and_aliases_are_valid():
    record = valid_record(external="public_net", source_net="internal_net")
    assert validate_one_to_one(record, "rules[0]") == ("iaas:opnsense:one-to-one-nat:edge:mail",)


@pytest.mark.parametrize("changes", [
    {"external": "198.51.100.0/24", "source_net": "192.0.2.0/25"},
    {"external": "2001:db8::/64"},
    {"source_net": "192.0.2.1/25"},
])
def test_invalid_binat_literals_fail(changes):
    with pytest.raises(ValidationError):
        validate_one_to_one(valid_record(**changes), "rules[0]")


def test_nat_does_not_require_equal_network_sizes():
    validate_one_to_one(valid_record(type="nat", source_net="192.0.2.0/25"), "rules[0]")


@pytest.mark.parametrize("interface", ["wan lan", "wan/lan", ""])
def test_interface_is_a_single_native_key(interface):
    with pytest.raises(ValidationError, match="interface"):
        validate_one_to_one(valid_record(interface=interface), "rules[0]")


def test_interface_preserves_mixed_case_group_reference():
    validate_one_to_one(valid_record(interface="Internal"), "rules[0]")


def test_absent_requires_only_identity_and_state():
    assert validate_one_to_one({"scope": "edge", "slug": "mail", "state": "absent"}, "rules[0]")
    extra = {"scope": "edge", "slug": "mail", "state": "absent", "enabled": True}
    with pytest.raises(ValidationError):
        validate_one_to_one(extra, "rules[0]")


@pytest.mark.parametrize("field", ["source_port", "destination_port", "target_port", "associated_rule", "description"])
def test_port_and_foreign_fields_are_rejected(field):
    record = valid_record()
    record[field] = "bad"
    with pytest.raises(ValidationError, match="unknown keys"):
        validate_one_to_one(record, "rules[0]")


def test_strict_types_and_reflection_enum():
    with pytest.raises(ValidationError):
        validate_one_to_one(valid_record(enabled=1), "rules[0]")
    with pytest.raises(ValidationError):
        validate_one_to_one(valid_record(nat_reflection="purenat"), "rules[0]")
