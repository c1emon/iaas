"""Offline validation for explicitly managed destination NAT rules."""

from __future__ import annotations

import ipaddress
import re
from typing import Any


DNAT_REQUIRED = {
    "scope",
    "slug",
    "state",
    "enabled",
    "sequence",
    "interface",
    "ip_protocol",
    "protocol",
    "source_net",
    "destination_net",
    "target",
    "nat_reflection",
    "associated_rule",
}
DNAT_OPTIONAL = {
    "source_port",
    "destination_port",
    "local_port",
    "source_invert",
    "destination_invert",
    "log",
    "pool_opts",
    "tag",
    "tagged",
}

IP_PROTOCOLS = {"inet", "inet6", "inet46"}
POOL_OPTIONS = {
    "",
    "round-robin",
    "round-robin sticky-address",
    "random",
    "random sticky-address",
    "source-hash",
    "bitmask",
}
REFLECTION_OPTIONS = {"", "purenat", "disable"}
ASSOCIATED_RULE_OPTIONS = {"", "pass", "rule"}
PORT_PROTOCOLS = {"tcp", "udp", "tcp/udp"}
# ProtocolField is populated from the fixed FreeBSD ``/etc/protocols`` list;
# these are the protocol values exposed by the pinned provider contract,
# including its synthetic TCP/UDP choice and IPv6 ICMP spelling.
PROTOCOLS = {
    "any", "tcp", "udp", "tcp/udp", "icmp", "ipv6-icmp", "icmpv6", "igmp", "gre", "esp", "ah",
    "ospf", "pim", "carp", "pfsync", "sctp", "udplite", "ipip", "ipencap", "l2tp", "rsvp",
    "eigrp", "pgm", "stp", "ipcomp", "etherip", "encap", "igp", "ggp", "rdp", "dccp",
}
RANGE = re.compile(r"^\d+-\d+$")


def _optional_string(value: Any, path: str) -> None:
    if not isinstance(value, str):
        from . import _error

        _error(path, "must be a string")


def _strict_text(value: Any, path: str) -> None:
    _optional_string(value, path)
    if any(char in value for char in " \t\n\r\0\v\f"):
        from . import _error

        _error(path, "must not contain spaces, newlines or control characters")


def _choice(value: Any, path: str, choices: set[str]) -> str:
    _optional_string(value, path)
    if value not in choices:
        from . import _error

        _error(path, "has unsupported value")
    return value


def _port(value: Any, path: str, *, allow_range: bool) -> None:
    """Validate the provider's string port syntax, including empty clears."""
    from . import _error, _ports

    if not isinstance(value, str):
        _error(path, "must be a string")
    if value == "":
        return
    _ports(value, path)
    if not allow_range and RANGE.fullmatch(value):
        _error(path, "local_port does not accept a port range")
    if not allow_range and value == "any":
        _error(path, "local_port must be a single port or alias")


def _address_token(
    value: Any,
    path: str,
    *,
    allow_any: bool = True,
    allow_self: bool = True,
    allow_network: bool = True,
) -> int | None:
    """Return a literal address family, leaving provider aliases unresolved."""
    from . import IDENTIFIER, _error, _string

    value = _string(value, path)
    if value == "any":
        if not allow_any:
            _error(path, "must be an IP/CIDR or valid object token")
        return None
    if value == "(self)":
        if not allow_self:
            _error(path, "must be an IP/CIDR or valid object token")
        return None
    try:
        if "/" in value:
            if not allow_network:
                _error(path, "must be an IP address or valid alias")
            parsed = ipaddress.ip_network(value, strict=False)
        else:
            parsed = ipaddress.ip_address(value)
    except ValueError:
        if "." in value or ":" in value:
            _error(path, "must be an IP/CIDR or valid object token")
        if not IDENTIFIER.fullmatch(value):
            _error(path, "must be an IP/CIDR or valid object token")
        return None
    return parsed.version


def _family_check(version: int | None, ip_protocol: str, path: str) -> None:
    if version is not None and ip_protocol != "inet46":
        expected = 4 if ip_protocol == "inet" else 6
        if version != expected:
            from . import _error

            _error(path, f"address family does not match {ip_protocol}")


def validate_dnat(record: dict[str, Any], path: str) -> tuple[str]:
    """Validate one DNAT declaration and return its stable managed identity."""
    from . import _boolean, _error, _integer, _list, _rule_interface, _shape, _string
    from .nat import nat_identity

    if not isinstance(record, dict):
        _error(path, "must be a mapping")

    state = record.get("state")
    required = {"scope", "slug", "state"} if state == "absent" else DNAT_REQUIRED
    _shape(record, path, required, DNAT_OPTIONAL if state != "absent" else set())
    identity = nat_identity(record, path, "dnat")
    if state == "absent":
        return identity

    _boolean(record["enabled"], f"{path}.enabled")
    _integer(record["sequence"], f"{path}.sequence", minimum=1, maximum=999999)

    interfaces = _list(record["interface"], f"{path}.interface")
    if not interfaces:
        _error(f"{path}.interface", "must not be empty")
    for index, interface in enumerate(interfaces):
        interface_path = f"{path}.interface[{index}]"
        _rule_interface(interface, interface_path)
        if interface == "lo0":
            _error(interface_path, "is not accepted by the DNAT provider")

    ip_protocol = _string(record["ip_protocol"], f"{path}.ip_protocol")
    if ip_protocol not in IP_PROTOCOLS:
        _error(f"{path}.ip_protocol", "must be inet, inet6 or inet46")

    protocol = _string(record["protocol"], f"{path}.protocol")
    protocol_lower = protocol.lower()
    if protocol_lower not in PROTOCOLS:
        _error(f"{path}.protocol", "is not a protocol exposed by the provider")

    source_version = _address_token(record["source_net"], f"{path}.source_net")
    destination_version = _address_token(record["destination_net"], f"{path}.destination_net")
    target_version = _address_token(
        record["target"], f"{path}.target", allow_any=False, allow_self=False, allow_network=False
    )
    _family_check(source_version, ip_protocol, f"{path}.source_net")
    _family_check(destination_version, ip_protocol, f"{path}.destination_net")
    _family_check(target_version, ip_protocol, f"{path}.target")

    for field in {"source_invert", "destination_invert", "log"} & record.keys():
        _boolean(record[field], f"{path}.{field}")
    # Only positive literal matches constrain the packet family.  An inverted
    # address excludes a set; aliases and interface tokens remain unresolved.
    families = {target_version} - {None}
    for field, version in (("source", source_version), ("destination", destination_version)):
        if version is not None and not record.get(f"{field}_invert", False):
            families.add(version)
    if len(families) > 1:
        _error(path, "address family conflicts between positive literal matches and target")

    if "source_port" in record:
        _port(record["source_port"], f"{path}.source_port", allow_range=True)
    if "destination_port" in record:
        _port(record["destination_port"], f"{path}.destination_port", allow_range=True)
    if "local_port" in record:
        _port(record["local_port"], f"{path}.local_port", allow_range=False)
    if any(record.get(field, "") != "" for field in ("source_port", "destination_port", "local_port")):
        if protocol_lower not in PORT_PROTOCOLS:
            _error(f"{path}.protocol", "ports require tcp, udp or tcp/udp")

    if "pool_opts" in record:
        _choice(record["pool_opts"], f"{path}.pool_opts", POOL_OPTIONS)
    if "nat_reflection" in record:
        _choice(record["nat_reflection"], f"{path}.nat_reflection", REFLECTION_OPTIONS)
    if "associated_rule" in record:
        _choice(record["associated_rule"], f"{path}.associated_rule", ASSOCIATED_RULE_OPTIONS)
    for field in {"tag", "tagged"} & record.keys():
        _strict_text(record[field], f"{path}.{field}")
    return identity
