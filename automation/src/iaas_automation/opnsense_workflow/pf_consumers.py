"""Bounded current-state checks for managed PF gateway and group consumers."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import ipaddress
from typing import Any

from .pf_rules import parse_loaded_pf_rules


def check_gateway_active(
    gateway: Mapping[str, Any],
    snapshot: Mapping[str, Any],
    consumers: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Check managed filter consumers' loaded ``route-to`` next hop.

    A consumer is related when its ``resource`` is ``filter-rules`` and its
    ``gateway`` equals the selected gateway name.  ``physical_interfaces`` is
    a caller-resolved set; a logical gateway interface is never treated as a
    physical PF interface.
    """
    name, next_hop, interfaces, reason = _gateway_contract(gateway)
    if reason:
        return _result("incomplete", reason)
    related, reason = _related_consumers(consumers, lambda row: (
        row.get("resource") == "filter-rules" and row.get("gateway") == name
    ))
    if related is None:
        return _result("incomplete", reason or "malformed_consumer_configuration")
    if not related:
        return _result("not_applicable", "complete_consumer_configuration_empty")
    loaded, reason = parse_loaded_pf_rules(snapshot)
    if loaded is None:
        return _result("incomplete", reason or "incomplete_pf_statistics")
    matches: list[dict[str, Any]] = []
    for consumer in related:
        active = [
            rule for rule in loaded
            if rule["section"] == "filter rules" and rule["uuid"] == consumer["uuid"]
        ]
        if not active:
            return _result("failed", "consumer_native_uuid_not_loaded", uuid=consumer["uuid"])
        for rule in active:
            route = rule.get("route_to")
            if route is None or route[0] not in interfaces or route[1] != next_hop:
                return _result("failed", "loaded_gateway_route_mismatch", uuid=consumer["uuid"])
            matches.append({"uuid": rule["uuid"], "pf_index": rule["pf_index"], "route_to": route})
    return _result("verified", "loaded_gateway_route_matches", matches=matches)


def check_interface_group_active(
    group: Mapping[str, Any],
    snapshot: Mapping[str, Any],
    consumers: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Check managed filter consumers' loaded ``on`` interface membership."""
    name, members, reason = _group_contract(group)
    if reason:
        return _result("incomplete", reason)
    if not isinstance(consumers, (list, tuple)):
        return _result("incomplete", "incomplete_consumer_configuration")
    for row in consumers:
        if not isinstance(row, Mapping):
            return _result("incomplete", "malformed_consumer_configuration")
        enabled = row.get("enabled")
        disabled = row.get("disabled")
        if (enabled is not None and type(enabled) is not bool) or (disabled is not None and type(disabled) is not bool):
            return _result("incomplete", "malformed_consumer_enabled_state")
        if disabled is True or enabled is False:
            continue
        if row.get("resource") in {"dnat", "one-to-one-nat"} and name in _as_strings(row.get("interface")):
            return _result("unsupported", "unsupported_nat_consumer_identity")
    related, reason = _related_consumers(consumers, lambda row: (
        row.get("resource") in {"filter-rules", "dnat", "one-to-one-nat"}
        and name in _as_strings(row.get("interface"))
    ))
    if related is None:
        return _result("incomplete", reason or "malformed_consumer_configuration")
    if not related:
        return _result("not_applicable", "complete_consumer_configuration_empty")
    if any(row.get("resource") != "filter-rules" for row in related):
        return _result("unsupported", "unsupported_nat_consumer_identity")
    loaded, reason = parse_loaded_pf_rules(snapshot)
    if loaded is None:
        return _result("incomplete", reason or "incomplete_pf_statistics")
    allowed = {name, *members}
    matches: list[dict[str, Any]] = []
    for consumer in related:
        active = [
            rule for rule in loaded
            if rule["section"] == "filter rules" and rule["uuid"] == consumer["uuid"]
        ]
        if not active:
            return _result("failed", "consumer_native_uuid_not_loaded", uuid=consumer["uuid"])
        loaded_on = {rule.get("on") for rule in active}
        if None in loaded_on or not loaded_on <= allowed:
            return _result("unknown", "loaded_interface_group_scope_unresolved", uuid=consumer["uuid"])
        if name not in loaded_on and not set(members).issubset(loaded_on):
            return _result("failed", "loaded_interface_group_members_mismatch", uuid=consumer["uuid"])
        for rule in active:
            matches.append({"uuid": rule["uuid"], "pf_index": rule["pf_index"], "on": rule["on"]})
    return _result("verified", "loaded_interface_group_matches", matches=matches)


def _gateway_contract(gateway: Mapping[str, Any]) -> tuple[str | None, str | None, set[str], str | None]:
    name = gateway.get("name")
    next_hop = gateway.get("gateway")
    if not isinstance(name, str) or not name or not isinstance(next_hop, str) or not next_hop:
        return None, None, set(), "malformed_gateway_configuration"
    try:
        ipaddress.ip_address(next_hop)
    except ValueError:
        return None, None, set(), "unsupported_gateway_next_hop"
    physical = gateway.get("physical_interfaces")
    if not isinstance(physical, list):
        return None, None, set(), "gateway_physical_interfaces_unavailable"
    interfaces = set(_as_strings(physical))
    if not interfaces:
        return None, None, set(), "gateway_physical_interfaces_unavailable"
    return name, next_hop, interfaces, None


def _group_contract(group: Mapping[str, Any]) -> tuple[str | None, tuple[str, ...], str | None]:
    name = group.get("name")
    members = group.get("members")
    if not isinstance(name, str) or not name or not isinstance(members, list):
        return None, (), "malformed_interface_group_configuration"
    if any(not isinstance(member, str) or not member for member in members):
        return None, (), "malformed_interface_group_members"
    return name, tuple(dict.fromkeys(members)), None


def _related_consumers(
    consumers: Sequence[Mapping[str, Any]], predicate: Any
) -> tuple[list[dict[str, Any]] | None, str | None]:
    if not isinstance(consumers, (list, tuple)):
        return None, "incomplete_consumer_configuration"
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in consumers:
        if not isinstance(row, Mapping):
            return None, "malformed_consumer_configuration"
        enabled = row.get("enabled")
        disabled = row.get("disabled")
        if enabled is not None and type(enabled) is not bool:
            return None, "malformed_consumer_enabled_state"
        if disabled is not None and type(disabled) is not bool:
            return None, "malformed_consumer_enabled_state"
        if disabled is True or enabled is False:
            continue
        if not predicate(row):
            continue
        uuid = row.get("uuid")
        if not isinstance(uuid, str) or not uuid:
            return None, "consumer_native_uuid_unavailable"
        if uuid in seen:
            return None, "duplicate_consumer_native_uuid"
        seen.add(uuid)
        result.append(dict(row) | {"uuid": uuid})
    return result, None


def _as_strings(value: Any) -> list[str]:
    values = value if isinstance(value, list) else [value]
    return [item for item in values if isinstance(item, str) and item]


def _result(status: str, reason: str, **extra: Any) -> dict[str, Any]:
    result: dict[str, Any] = {"status": status, "reason": reason}
    result.update(extra)
    return result
