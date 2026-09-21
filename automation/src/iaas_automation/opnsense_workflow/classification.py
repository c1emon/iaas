"""Evidence based classification for bounded OPNsense observations.

The reader receives rows from the pinned Collection's native list models.  This
module deliberately does not infer ownership from names, UUIDs, conversion
success, or changing member values.  A classification is metadata about the
native object and is independent from the standard configuration conversion.
"""

from __future__ import annotations

from copy import deepcopy
import ipaddress
import re
from typing import Any


ORIGINS = frozenset({"user_config", "system_builtin", "derived", "unknown"})
MANAGEMENT = frozenset({"independent", "via_source", "read_only", "unknown"})
REFERENCE_ROLES = frozenset({"address", "port", "interface-group"})

# These values are intentionally small and stable.  They describe evidence
# categories, never raw provider fields or exception text.
SUPPORTED_BASIS = frozenset({
    "supported_model",
    "native_internal_type",
    "native_external_type",
    "persistent_configuration",
    "dynamic_contents",
    "runtime_state",
    "reference_role_from_content",
    "complete_literal_membership",
    "native_static_child",
    "reference_role_from_native_identity",
    "classification_evidence_missing",
    "partial_management_unsupported",
})

_ALIAS_TYPES = frozenset({
    "host", "network", "port", "url", "urltable", "urljson", "geoip",
    "networkgroup", "mac", "dynipv6host", "external", "internal",
})
_DYNAMIC_ALIAS_TYPES = frozenset({"url", "urltable", "urljson", "geoip", "dynipv6host"})
_CRUD_RESOURCES = frozenset({
    "aliases", "vips", "gateways", "filter-rules", "dnat", "one-to-one-nat",
})

_PORT = re.compile(r"^[1-9][0-9]{0,4}(?:-[1-9][0-9]{0,4})?$")
_STATIC_GROUPS = {
    "openvpn": "OpenVPN (Group)",
    "enc0": "IPsec encapsulation",
    "wireguard": "WireGuard (Group)",
}


def _classification(
    origin: str,
    management: str,
    basis: list[str],
    *,
    source: str | None = None,
    reason: str | None = None,
) -> dict[str, Any]:
    if origin not in ORIGINS or management not in MANAGEMENT:
        raise ValueError("invalid classification value")
    unique_basis = list(dict.fromkeys(basis))
    if not unique_basis or any(item not in SUPPORTED_BASIS for item in unique_basis):
        raise ValueError("invalid classification basis")
    result: dict[str, Any] = {
        "origin": origin,
        "management": management,
        "basis": unique_basis,
    }
    if source is not None:
        result["source"] = source
    if reason is not None:
        result["reason"] = reason
    return result


def _finish(
    row: dict[str, Any],
    result: tuple[dict[str, Any], list[str]],
) -> tuple[dict[str, Any], list[str]]:
    """Fail closed when an optional native origin marker conflicts."""

    classification, nature = result
    marker = row.get("origin")
    if marker is not None and marker != classification["origin"]:
        return (_classification(
            "unknown", "unknown", ["classification_evidence_missing"],
            reason="conflicting_classification",
        ), nature)
    return classification, nature


def classify_resource(
    resource: str,
    row: dict[str, Any],
    *,
    identity: list[str] | None,
    configuration: dict[str, Any] | None,
    native_row: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], list[str]]:
    """Return classification and the separately scoped data nature.

    ``configuration`` is deliberately only used to preserve the distinction
    between a persistent object and a failed conversion.  It never grants
    management capability.
    """

    evidence_row = native_row or row

    if resource == "aliases":
        alias_type = row.get("type")
        if not isinstance(alias_type, str) or alias_type not in _ALIAS_TYPES:
            return _finish(evidence_row, (_classification(
                "unknown", "unknown", ["classification_evidence_missing"],
                reason="classification_evidence_missing",
            ), ["persistent_configuration"]))
        if alias_type == "internal":
            # The pinned Alias model treats internal aliases as native
            # objects and excludes them from ordinary existing-entry CRUD.
            return _finish(evidence_row, (_classification(
                "system_builtin", "read_only",
                ["native_internal_type", "persistent_configuration"],
            ), ["persistent_configuration"]))
        basis = ["supported_model", "persistent_configuration"]
        if alias_type == "external":
            basis.insert(1, "native_external_type")
        nature = ["persistent_configuration"]
        if alias_type in _DYNAMIC_ALIAS_TYPES:
            basis.append("dynamic_contents")
            nature.append("dynamic_contents")
        return _finish(evidence_row, (_classification("user_config", "independent", basis), nature))

    if resource == "interface-groups":
        native = native_row or row
        name = row.get("name")
        native_name = native.get("ifname", native.get("name"))
        native_uuid = native.get("uuid")
        sequence = row.get("sequence")
        description = row.get("description")
        native_members = native.get("members")
        # GroupField's fixed virtual children are materialized with uuid/name,
        # sequence and description from this exact static payload.  Require
        # every stable field and an empty member list; a matching name alone
        # is deliberately insufficient because users can create any group.
        if (isinstance(name, str) and name in _STATIC_GROUPS
                and native_name == name and native_uuid == name and sequence == 10
                and description == _STATIC_GROUPS[name]
                and native_members in (None, "", [], {})):
            return _finish(evidence_row, (_classification(
                "derived", "read_only",
                ["native_static_child", "persistent_configuration"],
                source="firewall/group/static-child",
            ), ["persistent_configuration"]))
        # The fixed Group model has CRUD operations, but it exposes no native
        # generated/read-only marker.  Names such as openvpn or wireguard are
        # therefore insufficient evidence and remain unknown.
        members = row.get("members")
        if isinstance(members, list) \
                and members and all(isinstance(item, str) and item for item in members):
            return _finish(evidence_row, (_classification(
                "user_config", "independent",
                ["supported_model", "persistent_configuration"],
            ), ["persistent_configuration"]))
        return _finish(evidence_row, (_classification(
            "unknown", "unknown", ["classification_evidence_missing"],
            reason="classification_evidence_missing",
        ), ["persistent_configuration"]))

    if resource in _CRUD_RESOURCES and identity:
        basis = ["supported_model", "persistent_configuration"]
        nature = ["persistent_configuration"]
        if resource == "gateways" and not row.get("gateway"):
            # A dynamic or missing address does not establish system origin or
            # read-only state.  A partial native override has no reliable
            # independent lifecycle proof, so keep management unknown.
            return _finish(evidence_row, (_classification(
                "unknown", "unknown", basis,
                reason="classification_evidence_missing",
            ), ["persistent_configuration", "runtime_state"]))
        return _finish(evidence_row, (_classification("user_config", "independent", basis), nature))

    return _finish(evidence_row, (_classification(
        "unknown", "unknown", ["classification_evidence_missing"],
        reason="classification_evidence_missing",
    ), ["persistent_configuration"]))


def _members(value: Any) -> list[str] | None:
    if isinstance(value, list) and all(isinstance(item, str) and item for item in value):
        return list(value)
    if isinstance(value, str):
        values = [item for item in re.split(r"[,\n]", value) if item]
        return values or None
    return None


def reference_support(
    resource: str,
    row: dict[str, Any],
    classification: dict[str, Any],
) -> dict[str, Any] | None:
    """Describe only verified roles for non-expressible system references."""

    if resource == "interface-groups" and classification.get("origin") == "derived":
        name = row.get("name")
        if isinstance(name, str) and name in _STATIC_GROUPS:
            return {
                "label": "interface-groups:" + name,
                "roles": ["interface-group"],
                "basis": ["native_static_child", "reference_role_from_native_identity"],
                "dependencies_complete": True,
            }
        return None
    if resource != "aliases" or classification.get("origin") != "system_builtin":
        return None
    name = row.get("name")
    if not isinstance(name, str) or not name:
        return None
    values = _members(row.get("content"))
    if not values:
        return None

    if all(_PORT.fullmatch(item) for item in values):
        role = "port"
        ip_protocol = None
    else:
        networks: list[ipaddress._BaseNetwork] = []
        for item in values:
            try:
                networks.append(ipaddress.ip_network(item, strict=False))
            except ValueError:
                return None
        versions = {network.version for network in networks}
        if len(versions) != 1:
            return None
        role = "address"
        ip_protocol = "inet" if versions == {4} else "inet6"

    result: dict[str, Any] = {
        "label": "aliases:" + name,
        "roles": [role],
        "basis": [
            "native_internal_type",
            "reference_role_from_content",
            "complete_literal_membership",
        ],
        "dependencies_complete": True,
    }
    if ip_protocol is not None:
        result["ip_protocol"] = ip_protocol
    return deepcopy(result)


__all__ = [
    "MANAGEMENT",
    "ORIGINS",
    "REFERENCE_ROLES",
    "SUPPORTED_BASIS",
    "classify_resource",
    "reference_support",
]
