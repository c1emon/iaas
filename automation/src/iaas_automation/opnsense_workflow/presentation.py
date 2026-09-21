"""Read-only presentation of complete OPNsense observations.

The reader owns the bounded observation and its classification.  This module
only creates a display projection; planning and execution must continue to use
the complete observation returned by the reader.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from iaas_automation.common.errors import require


CONFIGURATION_SCOPE = "configuration"
DISPLAY_SCOPE = "display"


def include_system_value(value: Any = False) -> bool:
    """Validate the read-only display switch without accepting truthy values."""
    require(type(value) is bool, "include_system must be a boolean")
    return value


def _classification(obj: dict[str, Any]) -> dict[str, Any]:
    value = obj.get("classification")
    if not isinstance(value, dict):
        return {"origin": "unknown", "management": "unknown", "basis": []}
    return value


def hidden_system_object(obj: dict[str, Any]) -> bool:
    classification = _classification(obj)
    return (classification.get("origin") in {"system_builtin", "derived"}
            and classification.get("management") in {"via_source", "read_only"})


def _selected_identities(selection: Any) -> set[tuple[str, ...]] | None:
    if selection == "all":
        return None
    if not isinstance(selection, list):
        return set()
    return {tuple(identity) for identity in selection if isinstance(identity, list)}


def _counts(objects: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    origins: dict[str, int] = {}
    management: dict[str, int] = {}
    for obj in objects:
        classification = _classification(obj)
        origin = classification.get("origin", "unknown")
        capability = classification.get("management", "unknown")
        origins[origin] = origins.get(origin, 0) + 1
        management[capability] = management.get(capability, 0) + 1
    return {"origin": origins, "management": management}


def _summary(observation: dict[str, Any], selected: list[dict[str, Any]], displayed: list[dict[str, Any]],
             hidden: int, filtered: bool) -> dict[str, Any]:
    objects = observation.get("objects", [])
    coverage = deepcopy(observation.get("coverage", {}))
    counts = _counts(selected)
    unsupported_user = sum(1 for obj in selected
                           if _classification(obj).get("origin") == "user_config"
                           and obj.get("configuration") is None)
    expressible_user = sum(1 for obj in selected
                          if _classification(obj).get("origin") == "user_config"
                          and obj.get("configuration") is not None)
    non_expressible_system = sum(1 for obj in selected
                                 if _classification(obj).get("origin") in {"system_builtin", "derived"}
                                 and obj.get("configuration") is None)
    expressible = sum(1 for obj in selected if obj.get("configuration") is not None)
    unknown_classification = sum(1 for obj in selected
                                if not isinstance(obj.get("classification"), dict)
                                or _classification(obj).get("origin") == "unknown"
                                or _classification(obj).get("management") == "unknown")
    reasons: dict[str, int] = {}
    for obj in selected:
        reason = obj.get("reason")
        values = reason if isinstance(reason, list) else [reason]
        for value in values:
            if isinstance(value, str) and value:
                reasons[value] = reasons.get(value, 0) + 1
    return {
        "enumerated_count": len(objects) if isinstance(objects, list) else 0,
        "enumerated_rows": coverage.get("rows"),
        "enumerated_total": coverage.get("total"),
        "selection_matched_count": len(selected),
        "displayed_count": len(displayed),
        "hidden_count": hidden,
        "display_filtered": filtered,
        "classification_counts": counts,
        "configuration_counts": {
            "expressible": expressible,
            "non_expressible": len(selected) - expressible,
            "user_config_failed": unsupported_user,
            "user_config_expressible": expressible_user,
            "system_or_derived_non_expressible": non_expressible_system,
            "unknown": unknown_classification,
        },
        "reason_counts": reasons,
        "coverage": coverage,
    }


def project_observations(observations: dict[str, dict[str, Any]], selection: dict[str, Any],
                         *, include_system: bool = False) -> dict[str, dict[str, Any]]:
    """Return a marked display projection without changing the source mapping.

    Explicit identity selections keep their object detail even when the normal
    class listing would hide that object.  ``all`` remains a class listing and
    therefore applies the default system projection.
    """
    include_system = include_system_value(include_system)
    require(isinstance(observations, dict) and isinstance(selection, dict),
            "workflow observations and selection must be mappings")
    result: dict[str, dict[str, Any]] = {}
    for resource, observation in observations.items():
        require(isinstance(observation, dict), "workflow observation must be a mapping")
        all_objects = observation.get("objects", [])
        require(isinstance(all_objects, list), "workflow observation objects must be a list")
        entries = selection.get(resource, "all")
        requested = _selected_identities(entries)
        matched = [obj for obj in all_objects
                   if isinstance(obj, dict)
                   and (requested is None or tuple(obj.get("identity", ())) in requested)]
        explicit = requested is not None
        displayed = [obj for obj in matched
                     if include_system or not hidden_system_object(obj) or explicit]
        hidden = len(matched) - len(displayed)
        projected = deepcopy(observation)
        projected["objects"] = deepcopy(displayed)
        if isinstance(entries, list):
            projected["selected_identities"] = deepcopy(entries)
        projected["observation_scope"] = DISPLAY_SCOPE
        projected["display_projection"] = {
            "include_system": include_system,
            "filtered": hidden > 0,
            "selected_scope": "explicit" if explicit else "all",
        }
        projected["summary"] = _summary(observation, matched, displayed, hidden, hidden > 0)
        result[resource] = projected
    return result


def display_result_metadata(observations: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Build result-level accountability metadata from a display projection."""
    return {
        "observation_scope": DISPLAY_SCOPE,
        "display_projection": True,
        "displayed_count": sum(item.get("summary", {}).get("displayed_count", 0)
                                for item in observations.values()),
        "hidden_count": sum(item.get("summary", {}).get("hidden_count", 0)
                             for item in observations.values()),
    }


__all__ = [
    "CONFIGURATION_SCOPE", "DISPLAY_SCOPE", "display_result_metadata",
    "hidden_system_object", "include_system_value", "project_observations",
]
