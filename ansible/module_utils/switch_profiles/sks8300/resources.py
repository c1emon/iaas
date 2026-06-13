"""SKS8300 declarative configuration resource registry."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from ..errors import SwitchProfileError


FORBIDDEN_COMMAND_RE = re.compile(
    r"\b(?:reload|erase(?:\s+\S+)?|write\s+erase|delete\s+startup-config|format(?:\s+\S+)?|"
    r"factory-default|reset(?:\s+\S+)?|boot\s+system)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ResourceField:
    """Field metadata for a declarative config resource."""

    name: str
    required: bool = False
    default: Any = None
    read_only: bool = False
    sensitive: bool = False
    choices: tuple[Any, ...] = ()


@dataclass(frozen=True)
class ResourceDefinition:
    """Resource metadata used for validation, diff, render, and verification."""

    name: str
    primary_key: str
    fields: Mapping[str, ResourceField]
    collect_subset: str
    allowed_operations: tuple[str, ...] = ("create", "update", "remove", "no-op")


VLAN_RESOURCE = ResourceDefinition(
    name="vlans",
    primary_key="id",
    collect_subset="vlans",
    fields={
        "id": ResourceField("id", required=True, read_only=True),
        "name": ResourceField("name", default=""),
        "state": ResourceField("state", default="present", choices=("present", "absent")),
        "status": ResourceField("status", read_only=True),
        "secret": ResourceField("secret", sensitive=True),
    },
)


INTERFACE_RESOURCE = ResourceDefinition(
    name="interfaces",
    primary_key="name",
    collect_subset="interfaces",
    fields={
        "name": ResourceField("name", required=True, read_only=True),
        "mode": ResourceField("mode", default="access", choices=("access", "trunk", "hybrid")),
        "access_vlan": ResourceField("access_vlan"),
        "tagged_vlans": ResourceField("tagged_vlans", default=[]),
        "untagged_vlans": ResourceField("untagged_vlans", default=[]),
        "state": ResourceField("state", default="present", choices=("present",)),
    },
    allowed_operations=("update", "no-op"),
)


RESOURCE_REGISTRY: dict[str, ResourceDefinition] = {
    VLAN_RESOURCE.name: VLAN_RESOURCE,
    INTERFACE_RESOURCE.name: INTERFACE_RESOURCE,
}


INTERFACE_NAME_RE = re.compile(
    r"^(?:Ethernet\d+/\d+/\d+|GigabitEthernet\d+/\d+/\d+|Ten-GigabitEthernet\d+/\d+/\d+)$"
)


def _as_sequence(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    raise SwitchProfileError("switch_config_intent resource values must be lists of mappings")


def _normalize_allowed_operations(allowed_operations: Sequence[str] | None) -> set[str]:
    if allowed_operations is None:
        return {"create", "update", "remove", "no-op"}
    normalized = {str(item).strip().lower() for item in allowed_operations if str(item).strip()}
    if not normalized:
        raise SwitchProfileError("switch_config_allowed_operations must contain at least one operation")
    unsupported = normalized - {"create", "update", "remove", "no-op"}
    if unsupported:
        raise SwitchProfileError(
            "Unsupported switch_config_allowed_operations values: " + ", ".join(sorted(unsupported))
        )
    return normalized


def _normalize_vlan_id(value: Any, field_name: str = "VLAN ID") -> int:
    try:
        vlan_id = int(value)
    except (TypeError, ValueError) as exc:
        raise SwitchProfileError(f"{field_name} must be an integer") from exc
    if vlan_id < 1 or vlan_id > 4094:
        raise SwitchProfileError(f"{field_name} {vlan_id} is outside supported range 1-4094")
    return vlan_id


def _normalize_vlan_list(value: Any, field_name: str) -> list[int]:
    if value is None:
        return []
    if not isinstance(value, (list, tuple)):
        raise SwitchProfileError(f"Field '{field_name}' must be a list of VLAN IDs")
    vlan_ids = [_normalize_vlan_id(item, field_name) for item in value]
    return sorted(set(vlan_ids))


def _normalize_primary_key(resource: str, definition: ResourceDefinition, entry: dict[str, Any]) -> Any:
    primary_value = entry.get(definition.primary_key)
    if primary_value is None:
        raise SwitchProfileError(f"Resource '{resource}' primary key '{definition.primary_key}' must be provided")
    if resource == "interfaces":
        name = str(primary_value).strip()
        if not INTERFACE_NAME_RE.match(name):
            raise SwitchProfileError(
                "Interface name must be an SKS8300 Ethernet-style port such as Ethernet1/0/3"
            )
        return name
    return _normalize_vlan_id(primary_value)


def _normalize_interface_entry(entry: dict[str, Any]) -> None:
    mode = str(entry.get("mode", "access")).strip().lower()
    entry["mode"] = mode
    if entry.get("access_vlan") not in (None, ""):
        entry["access_vlan"] = _normalize_vlan_id(entry["access_vlan"], "access_vlan")
    else:
        entry["access_vlan"] = None
    entry["tagged_vlans"] = _normalize_vlan_list(entry.get("tagged_vlans", []), "tagged_vlans")
    entry["untagged_vlans"] = _normalize_vlan_list(entry.get("untagged_vlans", []), "untagged_vlans")

    if mode == "access":
        if entry["access_vlan"] is None:
            raise SwitchProfileError("Interface mode 'access' requires access_vlan")
        if entry["tagged_vlans"] or entry["untagged_vlans"]:
            raise SwitchProfileError("Interface mode 'access' does not support tagged_vlans or untagged_vlans")
        entry.pop("tagged_vlans", None)
        entry.pop("untagged_vlans", None)
    elif mode == "trunk":
        if entry["access_vlan"] is not None or entry["untagged_vlans"]:
            raise SwitchProfileError("Interface mode 'trunk' supports tagged_vlans only")
        entry.pop("access_vlan", None)
        entry.pop("untagged_vlans", None)
    elif mode == "hybrid":
        if entry["access_vlan"] is not None:
            raise SwitchProfileError("Interface mode 'hybrid' supports tagged_vlans and untagged_vlans, not access_vlan")
        entry.pop("access_vlan", None)
    else:
        raise SwitchProfileError("Interface mode must be one of: access, trunk, hybrid")


def _redact_entry(definition: ResourceDefinition, entry: Mapping[str, Any]) -> dict[str, Any]:
    redacted: dict[str, Any] = {}
    for key, value in entry.items():
        field = definition.fields.get(key)
        redacted[key] = "<redacted>" if field and field.sensitive and value not in (None, "") else value
    return redacted


def normalize_intent(intent: Any) -> dict[str, list[dict[str, Any]]]:
    """Validate and normalize operator declarative intent."""
    if intent is None:
        return {}
    if not isinstance(intent, Mapping):
        raise SwitchProfileError("switch_config_intent must be a mapping of resource names to lists")
    if "commands" in intent or "switch_config_commands" in intent:
        raise SwitchProfileError(
            "Arbitrary configuration command lists are not supported; use declarative switch_config_intent resources."
        )

    normalized: dict[str, list[dict[str, Any]]] = {}
    for resource_name, entries_value in intent.items():
        resource = str(resource_name).strip().lower()
        if resource not in RESOURCE_REGISTRY:
            raise SwitchProfileError(
                f"Unsupported switch_config_intent resource '{resource_name}'. Supported resources: "
                + ", ".join(sorted(RESOURCE_REGISTRY))
            )
        definition = RESOURCE_REGISTRY[resource]
        entries: list[dict[str, Any]] = []
        seen_keys: set[Any] = set()
        for item in _as_sequence(entries_value):
            if not isinstance(item, Mapping):
                raise SwitchProfileError(f"Entries for resource '{resource}' must be mappings")
            unsupported_fields = set(item) - set(definition.fields)
            if unsupported_fields:
                raise SwitchProfileError(
                    f"Unsupported fields for resource '{resource}': " + ", ".join(sorted(unsupported_fields))
                )
            entry: dict[str, Any] = dict(item)
            for field_name, field in definition.fields.items():
                if field.required and field_name not in entry:
                    raise SwitchProfileError(f"Resource '{resource}' requires field '{field_name}'")
                if field_name not in entry and field.default is not None:
                    entry[field_name] = field.default
                if field.read_only and field_name in entry and field_name != definition.primary_key:
                    raise SwitchProfileError(f"Field '{field_name}' on resource '{resource}' is read-only")
                if field.choices and entry.get(field_name) not in field.choices:
                    raise SwitchProfileError(
                        f"Field '{field_name}' on resource '{resource}' must be one of: "
                        + ", ".join(str(choice) for choice in field.choices)
                    )
            primary_key = _normalize_primary_key(resource, definition, entry)
            entry[definition.primary_key] = primary_key
            if resource == "interfaces":
                _normalize_interface_entry(entry)
            if primary_key in seen_keys:
                raise SwitchProfileError(f"Duplicate resource '{resource}' primary key {primary_key}")
            seen_keys.add(primary_key)
            entries.append(entry)
        normalized[resource] = entries
    return normalized


def collect_subsets_for_intent(intent: Any) -> list[str]:
    """Return read-only gather subsets needed to plan the declared intent."""
    normalized = normalize_intent(intent)
    subsets = [RESOURCE_REGISTRY[name].collect_subset for name in normalized]
    return subsets or ["vlans"]


def config_gather_subsets_for_intent(intent: Any) -> list[str]:
    """Return parser gather subsets needed for declared configuration intent."""
    return collect_subsets_for_intent(intent)


def _current_resource_map(current_facts: Mapping[str, Any], resource_name: str) -> dict[Any, dict[str, Any]]:
    definition = RESOURCE_REGISTRY[resource_name]
    result: dict[Any, dict[str, Any]] = {}
    for item in current_facts.get(resource_name, []) or []:
        if not isinstance(item, Mapping):
            continue
        key = item.get(definition.primary_key)
        if key is None:
            continue
        current_entry = dict(item)
        if resource_name == "interfaces":
            current_entry["tagged_vlans"] = _normalize_vlan_list(current_entry.get("tagged_vlans", []), "tagged_vlans")
            current_entry["untagged_vlans"] = _normalize_vlan_list(
                current_entry.get("untagged_vlans", []), "untagged_vlans"
            )
            if current_entry.get("access_vlan") not in (None, ""):
                current_entry["access_vlan"] = _normalize_vlan_id(current_entry["access_vlan"], "access_vlan")
            result[str(key).strip()] = current_entry
            continue
        result[int(key)] = current_entry
    return result


def _operation_for_entry(
    definition: ResourceDefinition,
    current: Mapping[str, Any] | None,
    desired: Mapping[str, Any],
) -> tuple[str, dict[str, Any]]:
    state = str(desired.get("state", "present")).lower()
    if state == "absent":
        if current is None:
            return "no-op", {}
        return "remove", dict(current)
    if current is None:
        return "create", dict(desired)
    changes = {
        key: {"before": current.get(key, ""), "after": value}
        for key, value in desired.items()
        if key not in {definition.primary_key, "state"} and current.get(key, "") != value
    }
    if not changes:
        return "no-op", {}
    return "update", changes


def build_diff(
    current_facts: Mapping[str, Any],
    intent: Any,
    allowed_operations: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Build an idempotent resource diff from current state and desired intent."""
    normalized = normalize_intent(intent)
    return _build_diff(current_facts, normalized, allowed_operations)


def _build_diff(
    current_facts: Mapping[str, Any],
    normalized: Mapping[str, list[dict[str, Any]]],
    allowed_operations: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Build a diff from already-normalized resource intent."""
    allowed = _normalize_allowed_operations(allowed_operations)
    resource_diffs: list[dict[str, Any]] = []
    for resource_name, desired_entries in normalized.items():
        definition = RESOURCE_REGISTRY[resource_name]
        current_entries = _current_resource_map(current_facts, resource_name)
        for desired in desired_entries:
            primary_value = desired[definition.primary_key]
            current = current_entries.get(primary_value)
            operation, changes = _operation_for_entry(definition, current, desired)
            if operation not in definition.allowed_operations:
                raise SwitchProfileError(f"Operation '{operation}' is not supported for resource '{resource_name}'")
            if operation not in allowed:
                raise SwitchProfileError(
                    f"Operation '{operation}' for resource '{resource_name}' key '{primary_value}' is not allowed"
                )
            resource_diffs.append(
                {
                    "resource": resource_name,
                    "primary_key": definition.primary_key,
                    "primary_value": primary_value,
                    "operation": operation,
                    "current": _redact_entry(definition, current or {}),
                    "desired": _redact_entry(definition, desired),
                    "changes": changes,
                }
            )
    return {"resources": resource_diffs, "changed": any(item["operation"] != "no-op" for item in resource_diffs)}


def render_commands(diff: Mapping[str, Any]) -> list[str]:
    """Render candidate CLI commands from validated resource diffs."""
    commands: list[str] = []
    for item in diff.get("resources", []) or []:
        if item.get("resource") == "interfaces":
            commands.extend(_render_interface_commands(item))
            continue
        if item.get("resource") != "vlans":
            raise SwitchProfileError(f"No renderer for resource '{item.get('resource')}'")
        operation = item.get("operation")
        vlan_id = int(item.get("primary_value"))
        desired = item.get("desired", {}) or {}
        if operation == "create":
            commands.append(f"vlan {vlan_id}")
            if desired.get("name"):
                commands.append(f"name {desired['name']}")
            commands.append("exit")
        elif operation == "update":
            commands.append(f"vlan {vlan_id}")
            if "name" in (item.get("changes", {}) or {}):
                commands.append(f"name {desired.get('name', '')}")
            commands.append("exit")
        elif operation == "remove":
            commands.append(f"no vlan {vlan_id}")
        elif operation == "no-op":
            continue
    return commands


def _format_vlan_list(vlan_ids: Sequence[int]) -> str:
    return ",".join(str(vlan_id) for vlan_id in sorted(set(int(item) for item in vlan_ids)))


def _format_legacy_vlan_list(vlan_ids: Sequence[int]) -> str:
    return ";".join(str(vlan_id) for vlan_id in sorted(set(int(item) for item in vlan_ids)))


def _normalize_interface_mode(value: Any) -> str:
    return str(value or "unknown").strip().lower()


def _render_interface_mode_transition(current_mode: Any, desired_mode: Any) -> list[str]:
    """Render SKS8300-safe switchport mode transition commands."""
    current = _normalize_interface_mode(current_mode)
    desired = _normalize_interface_mode(desired_mode)
    if current == desired:
        return []
    transitions: dict[tuple[str, str], list[str]] = {
        ("access", "trunk"): ["switchport mode trunk"],
        ("access", "hybrid"): ["switchport mode hybrid"],
        ("trunk", "access"): ["switchport mode access"],
        ("trunk", "hybrid"): ["switchport mode access", "switchport mode hybrid"],
        ("hybrid", "access"): ["switchport mode access"],
        ("hybrid", "trunk"): ["switchport mode trunk"],
        ("unknown", "access"): ["switchport mode access"],
        ("unknown", "trunk"): ["switchport mode trunk"],
        ("unknown", "hybrid"): ["switchport mode hybrid"],
        ("", "access"): ["switchport mode access"],
        ("", "trunk"): ["switchport mode trunk"],
        ("", "hybrid"): ["switchport mode hybrid"],
    }
    try:
        return transitions[(current, desired)]
    except KeyError as exc:
        raise SwitchProfileError(f"Unsupported interface mode transition: {current} -> {desired}") from exc


def _render_interface_commands(item: Mapping[str, Any]) -> list[str]:
    operation = item.get("operation")
    if operation == "no-op":
        return []
    if operation != "update":
        raise SwitchProfileError(f"Operation '{operation}' is not supported for resource 'interfaces'")

    desired = item.get("desired", {}) or {}
    current = item.get("current", {}) or {}
    changes = item.get("changes", {}) or {}
    name = desired.get("name") or item.get("primary_value")
    mode = desired.get("mode")
    commands = [f"interface {name}"]
    if "mode" in changes:
        commands.extend(_render_interface_mode_transition(current.get("mode"), mode))
    mode_changed = "mode" in changes
    if mode == "access" and (mode_changed or "access_vlan" in changes):
        commands.append(f"switchport access vlan {desired['access_vlan']}")
    if mode == "trunk" and (mode_changed or "tagged_vlans" in changes):
        vlan_list = _format_legacy_vlan_list(desired.get("tagged_vlans", []))
        commands.append(f"switchport trunk allowed vlan {vlan_list}" if vlan_list else "no switchport trunk allowed vlan")
    if mode == "hybrid":
        if mode_changed or "tagged_vlans" in changes:
            vlan_list = _format_legacy_vlan_list(desired.get("tagged_vlans", []))
            command = f"switchport hybrid allowed vlan {vlan_list} tag" if vlan_list else "no switchport hybrid allowed vlan tag"
            commands.append(command)
        if mode_changed or "untagged_vlans" in changes:
            vlan_list = _format_legacy_vlan_list(desired.get("untagged_vlans", []))
            command = (
                f"switchport hybrid allowed vlan {vlan_list} untag"
                if vlan_list
                else "no switchport hybrid allowed vlan untag"
            )
            commands.append(command)
    commands.append("exit")
    return commands

def assert_safe_rendered_commands(commands: Sequence[str]) -> None:
    """Fail fast if rendered commands contain forbidden destructive patterns."""
    for command in commands:
        if FORBIDDEN_COMMAND_RE.search(command or ""):
            raise SwitchProfileError(f"Rendered command is forbidden by safety policy: {command}")


def _vlan_collection_config(desired: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "vlan_id": int(desired["id"]),
        "name": desired.get("name", "") or "",
        "state": "active",
    }


def _l2_interface_collection_config(desired: Mapping[str, Any]) -> dict[str, Any]:
    mode = str(desired.get("mode", "access")).strip().lower()
    config: dict[str, Any] = {"name": desired["name"], "mode": mode}
    if mode == "access":
        config["access_vlan"] = int(desired["access_vlan"])
        config["pvid"] = int(desired["access_vlan"])
    elif mode == "trunk":
        config["trunk_allowed_vlan"] = _format_vlan_list(desired.get("tagged_vlans", [])) or None
    elif mode == "hybrid":
        tagged = _format_vlan_list(desired.get("tagged_vlans", []))
        untagged = _format_vlan_list(desired.get("untagged_vlans", []))
        if tagged:
            config["hybrid_tagged_vlan"] = tagged
        if untagged:
            config["hybrid_untagged_vlan"] = untagged
            config["pvid"] = int(str(untagged).split(",", maxsplit=1)[0])
    return {key: value for key, value in config.items() if value is not None}


def build_collection_operations(plan: Mapping[str, Any]) -> dict[str, Any]:
    """Map repository resource diffs to lifecycle-safe c1emon.xikeos module calls."""
    operations = {
        "vlan_merge_config": [],
        "vlan_delete_config": [],
        "l2_interface_merge_config": [],
        "unsupported": [],
        "modules": [
            "c1emon.xikeos.xikeos_vlans",
            "c1emon.xikeos.xikeos_l2_interfaces",
        ],
        "fallback_config_module": None,
    }
    for item in plan.get("diff", {}).get("resources", []) or []:
        operation = item.get("operation")
        if operation == "no-op":
            continue
        resource = item.get("resource")
        desired = item.get("desired", {}) or {}
        if resource == "vlans":
            if operation in {"create", "update"}:
                operations["vlan_merge_config"].append(_vlan_collection_config(desired))
            elif operation == "remove":
                operations["vlan_delete_config"].append({"vlan_id": int(item["primary_value"])})
            else:
                operations["unsupported"].append(item)
        elif resource == "interfaces":
            if operation == "update":
                operations["l2_interface_merge_config"].append(_l2_interface_collection_config(desired))
            else:
                operations["unsupported"].append(item)
        else:
            operations["unsupported"].append(item)

    module_commands = list(plan.get("rendered_commands", []) or [])
    assert_safe_rendered_commands(module_commands)
    operations["module_command_summaries"] = [re.sub(r"\s+", " ", command).strip() for command in module_commands]
    return operations


def build_plan(
    current_facts: Mapping[str, Any],
    intent: Any,
    allowed_operations: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Build a redacted plan/diff report with rendered candidate commands."""
    normalized = normalize_intent(intent)
    diff = _build_diff(current_facts, normalized, allowed_operations)
    commands = render_commands(diff)
    assert_safe_rendered_commands(commands)
    return {
        "current": {name: current_facts.get(name, []) for name in normalized},
        "desired": {
            name: [_redact_entry(RESOURCE_REGISTRY[name], item) for item in entries]
            for name, entries in normalized.items()
        },
        "diff": diff,
        "rendered_commands": commands,
        "rendered_command_summaries": [re.sub(r"\s+", " ", command).strip() for command in commands],
        "collection": build_collection_operations({"diff": diff, "rendered_commands": commands}),
        "changed": diff["changed"],
        "apply": {"enabled": False, "status": "not_requested"},
        "verify": {"status": "not_run"},
    }


def verify_intent(current_facts: Mapping[str, Any], intent: Any) -> dict[str, Any]:
    """Verify current state satisfies desired present/absent resource intent."""
    normalized = normalize_intent(intent)
    failures: list[dict[str, Any]] = []
    for resource_name, desired_entries in normalized.items():
        definition = RESOURCE_REGISTRY[resource_name]
        current_entries = _current_resource_map(current_facts, resource_name)
        for desired in desired_entries:
            primary_value = desired[definition.primary_key]
            current = current_entries.get(primary_value)
            state = desired.get("state", "present")
            if state == "absent" and current is not None:
                failures.append({"resource": resource_name, "primary_value": primary_value, "reason": "still present"})
                continue
            if state == "present" and current is None:
                failures.append({"resource": resource_name, "primary_value": primary_value, "reason": "missing"})
                continue
            if state == "present":
                for key, value in desired.items():
                    if key in {definition.primary_key, "state"}:
                        continue
                    if current and current.get(key, "") != value:
                        failures.append(
                            {
                                "resource": resource_name,
                                "primary_value": primary_value,
                                "field": key,
                                "expected": value,
                                "actual": current.get(key, "") if current else None,
                            }
                        )
    return {"ok": not failures, "status": "passed" if not failures else "failed", "failures": failures}
