"""Offline validation for OPNsense firewall interface groups."""

from __future__ import annotations

import re
from typing import Any

from . import _boolean, _error, _integer, _shape, _state, _string


GROUP_NAME = re.compile(r"^(?![0-9])[A-Za-z0-9_]{1,15}(?<![0-9])$")
# InterfaceField supplies configured interface keys directly and does not
# translate labels.  Keep this lexical check permissive for device/virtual
# names while rejecting whitespace and structured/nested values.
INTERFACE_KEY = re.compile(r"^[A-Za-z_][A-Za-z0-9_.-]*$")


def validate_interface_group(record: dict[str, Any], path: str) -> tuple[str]:
    """Validate one interface group and return its native-name identity."""
    common = {"name", "state"}
    optional = {"members", "gui_group", "sequence", "description"}
    _shape(record, path, common, optional)
    name = _string(record["name"], f"{path}.name")
    if not GROUP_NAME.fullmatch(name):
        _error(f"{path}.name", "must be 1..15 letters/digits/underscores and not end in a digit")
    state = _state(record["state"], f"{path}.state")
    if state == "absent":
        _shape(record, path, common)
        return (name,)

    _shape(record, path, common | {"members", "gui_group", "sequence"}, {"description"})
    members = record["members"]
    if not isinstance(members, list) or not members:
        _error(f"{path}.members", "must be a non-empty list")
    seen: set[str] = set()
    for index, member in enumerate(members):
        member_path = f"{path}.members[{index}]"
        member = _string(member, member_path)
        if not INTERFACE_KEY.fullmatch(member):
            _error(member_path, "must be a physical interface key")
        if member == name:
            _error(member_path, "nested/self-referencing groups are not supported")
        if member in seen:
            _error(member_path, "members must be unique")
        seen.add(member)
    _boolean(record["gui_group"], f"{path}.gui_group")
    _integer(record["sequence"], f"{path}.sequence", minimum=0, maximum=9999)
    if "description" in record and not isinstance(record["description"], str):
        _error(f"{path}.description", "must be a string")
    return (name,)
