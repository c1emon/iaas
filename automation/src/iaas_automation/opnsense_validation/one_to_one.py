"""Offline validation for OPNsense one-to-one NAT declarations."""

from __future__ import annotations

import ipaddress
import re
from typing import Any

from . import IDENTIFIER, _boolean, _error, _integer, _shape, _state, _string
from .nat import nat_identity


_ADDRESS_LIKE = re.compile(r"[0-9.:]+")
# InterfaceField supplies configured interface keys directly and does not
# translate labels.  Keep the lexical check permissive for virtual/device
# names while rejecting whitespace and structured/nested values.
INTERFACE_KEY = re.compile(r"^[A-Za-z_][A-Za-z0-9_.-]*$")


def _ipv4_network(value: Any, path: str, *, allow_special: bool = True) -> ipaddress.IPv4Network | None:
    """Validate a literal IPv4 value, while leaving legal aliases unresolved."""
    value = _string(value, path)
    try:
        network = ipaddress.ip_network(value, strict=False)
    except ValueError:
        if value in {"any", "(self)"}:
            if not allow_special:
                _error(path, "wildcard values are not valid here")
            return None
        if IDENTIFIER.fullmatch(value):
            if _ADDRESS_LIKE.fullmatch(value):
                _error(path, "must be an IPv4 address/CIDR or legal alias")
            return None
        _error(path, "must be an IPv4 address/CIDR or legal alias")
    if network.version != 4:
        _error(path, "IPv6/NPTv6 values are not supported")
    return network


PRESENT_REQUIRED = {
    "scope", "slug", "state", "enabled", "sequence", "interface", "type",
    "external", "source_net", "destination_net", "nat_reflection",
}
PRESENT_OPTIONAL = {"source_invert", "destination_invert", "log"}


def validate_one_to_one(record: dict[str, Any], path: str) -> tuple[str]:
    """Validate one declaration and return its stable NAT identity."""
    common = {"scope", "slug", "state"}
    state = _state(record.get("state"), f"{path}.state")
    if state == "absent":
        _shape(record, path, common)
        return nat_identity(record, path, "one-to-one-nat")

    _shape(record, path, PRESENT_REQUIRED, PRESENT_OPTIONAL)
    _boolean(record["enabled"], f"{path}.enabled")
    _integer(record["sequence"], f"{path}.sequence", minimum=1, maximum=99999)
    interface = _string(record["interface"], f"{path}.interface")
    if not INTERFACE_KEY.fullmatch(interface):
        _error(f"{path}.interface", "must be one interface or group key")
    kind = _string(record["type"], f"{path}.type")
    if kind not in {"nat", "binat"}:
        _error(f"{path}.type", "must be nat or binat")

    external = _ipv4_network(record["external"], f"{path}.external", allow_special=False)
    source = _ipv4_network(record["source_net"], f"{path}.source_net")
    _ipv4_network(record["destination_net"], f"{path}.destination_net")
    if kind == "binat" and external is not None and source is not None and external.prefixlen != source.prefixlen:
        _error(path, "BINAT external and source networks must have equal sizes")

    for field in PRESENT_OPTIONAL:
        if field in record:
            _boolean(record[field], f"{path}.{field}")
    reflection = _string(record["nat_reflection"], f"{path}.nat_reflection")
    if reflection not in {"enable", "disable"}:
        _error(f"{path}.nat_reflection", "must be enable or disable")
    return nat_identity(record, path, "one-to-one-nat")
