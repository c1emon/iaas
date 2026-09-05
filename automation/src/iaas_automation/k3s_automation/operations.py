"""Pure offline validation for explicitly scoped K3s operations.

This module deliberately does not load files, contact hosts, or mutate a
cluster.  It validates the operation boundary against an already composed
K3s model and, for upgrades, an operator-supplied observation of node
versions.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from iaas_automation.common.errors import ValidationError, require


_K3S_VERSION_RE = re.compile(r"^v(?P<major>\d+)\.(?P<minor>\d+)\.(?P<patch>\d+)\+k3s(?P<release>\d+)$")
_FORBIDDEN_SCOPE_TOKENS = {"all", "*", "all_hosts", "all-hosts", "pve_vms", "pve-vms"}


@dataclass(frozen=True)
class UpgradePlan:
    """Validated serial upgrade decision for one exact whole-cluster scope."""

    scope: tuple[str, ...]
    target_version: str
    skipped: tuple[str, ...]
    to_upgrade: tuple[str, ...]


def _declared_nodes(model: Mapping[str, Any]) -> tuple[Mapping[str, Any], ...]:
    raw_nodes_value = model.get("nodes")
    if not isinstance(raw_nodes_value, list) or not raw_nodes_value:
        raise ValidationError("composed model nodes: must be a non-empty list")
    raw_nodes = raw_nodes_value
    nodes: list[Mapping[str, Any]] = []
    seen: set[str] = set()
    for index, raw_node in enumerate(raw_nodes):
        require(isinstance(raw_node, Mapping), f"composed model nodes[{index}]: expected mapping")
        vm_ref = raw_node.get("vm_ref")
        require(isinstance(vm_ref, str) and vm_ref, f"composed model nodes[{index}].vm_ref: must be non-empty")
        require(vm_ref not in seen, f"composed model nodes[{index}].vm_ref: duplicate {vm_ref}")
        seen.add(vm_ref)
        nodes.append(raw_node)
    return tuple(nodes)


def validate_exact_scope(model: Mapping[str, Any], scope: str) -> tuple[str, ...]:
    """Validate and return an explicit comma-separated scope.

    Scope values are intentionally strict: each item must be an exact
    composed-model VM reference with no whitespace, wildcard, group alias, or
    duplicate.  In particular, an omitted scope is not interpreted as all
    hosts.
    """

    require(isinstance(scope, str), "scope: must be an explicit comma-separated string")
    require(scope != "", "scope: must be non-empty and explicit")
    items = scope.split(",")
    require(all(item != "" for item in items), "scope: empty node reference is not allowed")
    require(all(item == item.strip() for item in items), "scope: node references must not contain whitespace")
    require(all(item and not any(character.isspace() for character in item) for item in items), "scope: node references must not contain whitespace")
    require(all(item not in _FORBIDDEN_SCOPE_TOKENS and not any(marker in item for marker in ("*", "?", "[", "]")) for item in items), "scope: wildcards and implicit all-host aliases are not allowed")
    require(len(items) == len(set(items)), "scope: duplicate node references are not allowed")

    declared = tuple(node["vm_ref"] for node in _declared_nodes(model))
    declared_set = set(declared)
    unknown = sorted(set(items) - declared_set)
    require(not unknown, f"scope: unknown declared node reference(s): {', '.join(unknown)}")
    return tuple(items)


def validate_scope(model: Mapping[str, Any], scope: str) -> tuple[str, ...]:
    """Compatibility spelling for :func:`validate_exact_scope`."""

    return validate_exact_scope(model, scope)


def _require_whole_cluster(model: Mapping[str, Any], scope: str, operation: str) -> tuple[str, ...]:
    selected = validate_exact_scope(model, scope)
    declared = tuple(node["vm_ref"] for node in _declared_nodes(model))
    require(
        set(selected) == set(declared),
        f"{operation} scope: must explicitly select all declared nodes (whole cluster); partial scope is not allowed",
    )
    return selected


def validate_deployment_scope(model: Mapping[str, Any], scope: str) -> tuple[str, ...]:
    """Validate deployment's explicit whole-cluster mutation scope."""

    return _require_whole_cluster(model, scope, "deployment")


def validate_upgrade_scope(model: Mapping[str, Any], scope: str) -> tuple[str, ...]:
    """Validate upgrade's explicit whole-cluster mutation scope."""

    return _require_whole_cluster(model, scope, "upgrade")


def _version(value: Any, context: str) -> tuple[int, int, int, int]:
    require(isinstance(value, str), f"{context}: must be an exact K3s version")
    match = _K3S_VERSION_RE.fullmatch(value)
    require(match is not None, f"{context}: must be an exact vX.Y.Z+k3sN version")
    assert match is not None
    return tuple(int(match.group(name)) for name in ("major", "minor", "patch", "release"))  # type: ignore[return-value]


def _observations(
    model_nodes: tuple[Mapping[str, Any], ...],
    scope: tuple[str, ...],
    observed_versions: Mapping[str, str],
) -> dict[str, str]:
    require(isinstance(observed_versions, Mapping), "observed_versions: must map every scoped node to its version")
    expected = set(scope)
    actual = set(observed_versions)
    missing = sorted(expected - actual)
    extra = sorted(actual - expected)
    require(not missing, f"observed_versions: missing scoped node(s): {', '.join(missing)}")
    require(not extra, f"observed_versions: unknown node(s): {', '.join(extra)}")
    return {node["vm_ref"]: observed_versions[node["vm_ref"]] for node in model_nodes if node["vm_ref"] in expected}


def validate_upgrade(
    model: Mapping[str, Any],
    scope: str,
    observed_versions: Mapping[str, str],
    target_version: str,
) -> UpgradePlan:
    """Validate a resumable, one-minor-at-a-time whole-cluster upgrade.

    An observed cluster may be wholly on a prior version, wholly on target, or
    in the only resumable mixed state: exact target plus one exact prior
    version.  Every non-target node must reach target within its current
    Kubernetes minor or by one minor, and full K3s version ordering also
    prevents downgrades.
    """

    model_nodes = _declared_nodes(model)
    selected = validate_upgrade_scope(model, scope)
    target = _version(target_version, "upgrade target")
    observations = _observations(model_nodes, selected, observed_versions)
    parsed = {node: _version(version, f"observed_versions.{node}") for node, version in observations.items()}

    above_target = sorted(node for node, current in parsed.items() if current > target)
    require(not above_target, f"upgrade: downgrade/above target is not allowed for node(s): {', '.join(above_target)}")

    invalid_minor = sorted(
        node
        for node, current in parsed.items()
        if current[0] != target[0] or target[1] - current[1] not in {0, 1}
    )
    require(not invalid_minor, f"upgrade: skipped-minor or unsupported transition for node(s): {', '.join(invalid_minor)}")

    versions = set(parsed.values())
    lower_versions = versions - {target}
    require(
        len(lower_versions) <= 1,
        "upgrade: unsupported mixed versions; only one exact prior version may coexist with the exact target",
    )

    by_ref = {node["vm_ref"]: node for node in model_nodes}
    skipped = tuple(node for node in selected if parsed[node] == target)
    pending_servers = tuple(node for node in selected if parsed[node] != target and by_ref[node].get("role") == "server")
    pending_agents = tuple(node for node in selected if parsed[node] != target and by_ref[node].get("role") == "agent")
    return UpgradePlan(
        scope=selected,
        target_version=target_version,
        skipped=skipped,
        to_upgrade=pending_servers + pending_agents,
    )


def plan_upgrade(
    model: Mapping[str, Any],
    scope: str,
    observed_versions: Mapping[str, str],
    target_version: str,
) -> UpgradePlan:
    """Compatibility spelling for :func:`validate_upgrade`."""

    return validate_upgrade(model, scope, observed_versions, target_version)


__all__ = [
    "UpgradePlan",
    "parse_scope",
    "plan_upgrade",
    "validate_deployment_scope",
    "validate_exact_scope",
    "validate_scope",
    "validate_upgrade",
    "validate_upgrade_scope",
]


def parse_scope(model: Mapping[str, Any], scope: str) -> tuple[str, ...]:
    """Compatibility spelling for :func:`validate_exact_scope`."""

    return validate_exact_scope(model, scope)
