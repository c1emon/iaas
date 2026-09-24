import pytest

from iaas.common.errors import ValidationError
from iaas.opnsense_validation import validate_document
from iaas.opnsense_validation.interface_groups import validate_interface_group


def valid_record(**changes):
    record = {
        "name": "Internal",
        "state": "present",
        "members": ["lan", "opt1"],
        "gui_group": True,
        "sequence": 0,
    }
    record.update(changes)
    return record


def test_group_name_is_native_case_and_identity():
    assert validate_interface_group(valid_record(description="inside"), "groups[0]") == ("Internal",)
    assert validate_interface_group(valid_record(name="A"), "groups[0]") == ("A",)


def test_absent_requires_only_name_and_state():
    assert validate_interface_group({"name": "Internal", "state": "absent"}, "groups[0]") == ("Internal",)
    with pytest.raises(ValidationError):
        validate_interface_group(valid_record(state="absent"), "groups[0]")


@pytest.mark.parametrize("name", ["", "ends9", "a" * 16, "bad-name", "bad name"])
def test_invalid_group_names_fail(name):
    with pytest.raises(ValidationError):
        validate_interface_group(valid_record(name=name), "groups[0]")


@pytest.mark.parametrize("members", [[], ["lan", "lan"], [["lan"]], [""], ["lan/opt1"], ["lan opt1"]])
def test_invalid_members_fail(members):
    with pytest.raises(ValidationError):
        validate_interface_group(valid_record(members=members), "groups[0]")


def test_self_nested_group_is_rejected():
    with pytest.raises(ValidationError, match="nested"):
        validate_interface_group(valid_record(members=["Internal"]), "groups[0]")


@pytest.mark.parametrize("field,value", [("gui_group", 1), ("sequence", True), ("sequence", 10000)])
def test_strict_gui_and_sequence_validation(field, value):
    with pytest.raises(ValidationError):
        validate_interface_group(valid_record(**{field: value}), "groups[0]")


def test_foreign_fields_and_description_type_are_rejected():
    with pytest.raises(ValidationError, match="unknown keys"):
        validate_interface_group(valid_record(enabled=True), "groups[0]")
    with pytest.raises(ValidationError, match="description"):
        validate_interface_group(valid_record(description=False), "groups[0]")


@pytest.mark.parametrize("reverse", [False, True])
def test_single_document_rejects_nested_groups_in_either_order(reverse):
    records = [valid_record(name="Inner", members=["lan"]),
               valid_record(name="Outer", members=["Inner"])]
    if reverse:
        records.reverse()
    with pytest.raises(ValidationError, match="nested interface groups"):
        validate_document("interface-groups", {"opnsense_interface_groups": records})
