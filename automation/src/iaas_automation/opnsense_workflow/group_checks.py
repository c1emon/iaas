"""Read-only current-state checks for one OPNsense interface group.

The check combines two fixed 26.7.3 observations supplied by the caller:

* ``overview`` is the decoded ``interfaces/overview/interfaces_info`` result.
  Its rows identify a configured logical interface with ``identifier`` and its
  current device with ``device``.
* ``ifconfig`` is the decoded ``diagnostics/interface/get_interface_config``
  result.  It is keyed by device name and carries the kernel interface
  ``groups`` list.

The function only compares the current kernel interface-group membership with
the requested saved members.  It does not call an API, reload PF, or infer
that a particular reconfigure operation or loaded filter rule consumed the
new membership.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, TypeGuard


def check_interface_group_current(
    desired: Mapping[str, Any],
    overview: Any,
    ifconfig: Any,
    consumer_observation: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Compare one saved group with current kernel interface-group membership.

    ``desired`` is a normalized interface-group row with a non-empty ``name``
    and list-valued logical ``members``.  ``overview`` may be the complete
    list returned by the overview endpoint or its complete ``rows`` response;
    ``ifconfig`` must be the complete device-keyed response from diagnostics.

    The returned ``status`` is ``verified`` only for exact current membership,
    ``failed`` for a complete observation that disagrees, and ``unknown`` when
    either observation is malformed, incomplete, missing, or ambiguous.  An
    optional ``consumer_observation`` can be supplied by a separate fixed PF
    rule checker.  Its status must be ``verified``, ``not_applicable``,
    ``failed``, ``unknown``, ``incomplete`` or ``unsupported``.  The result always scopes the
    evidence to ``current_state`` and records that operation completion was
    not observed.
    """

    if not isinstance(desired, Mapping):
        return _unknown("malformed_desired_group")

    group_name = _text(desired.get("name"))
    members = desired.get("members")
    if group_name is None:
        return _unknown("group_name_unavailable")
    if not _member_list(members):
        return _unknown("malformed_group_members")
    logical_members = tuple(members)
    if len(set(logical_members)) != len(logical_members):
        return _unknown("duplicate_group_members")

    mapping, reason = _overview_mapping(overview)
    if mapping is None:
        return _unknown(reason or "malformed_interface_overview")

    physical_members: list[str] = []
    for logical in logical_members:
        physical = mapping.get(logical)
        if physical is None:
            return _unknown(
                "logical_interface_unmapped",
                expected={"group": group_name, "logical_members": list(logical_members)},
                observed={"logical_to_physical": mapping},
            )
        physical_members.append(physical)

    ifconfig_rows, reason = _ifconfig_rows(ifconfig)
    if ifconfig_rows is None:
        return _unknown(
            reason or "malformed_interface_diagnostics",
            expected={
                "group": group_name,
                "logical_members": list(logical_members),
                "physical_members": physical_members,
            },
            observed={"logical_to_physical": mapping},
        )

    expected_physical = set(physical_members)
    missing_devices = sorted(expected_physical - set(ifconfig_rows))
    if missing_devices:
        return _unknown(
            "diagnostic_interface_missing",
            expected={
                "group": group_name,
                "logical_members": list(logical_members),
                "physical_members": sorted(expected_physical),
            },
            observed={"missing_devices": missing_devices},
        )
    observed_physical = {
        device for device, details in ifconfig_rows.items() if group_name in details["groups"]
    }
    expected = {
        "group": group_name,
        "logical_members": list(logical_members),
        "physical_members": sorted(expected_physical),
    }
    observed = {
        "group_members": sorted(observed_physical),
        "interfaces": {
            device: list(details["groups"])
            for device, details in sorted(ifconfig_rows.items())
        },
    }
    if observed_physical != expected_physical:
        return _with_consumer(_result(
            "failed",
            "current_group_membership_mismatch",
            expected=expected,
            observed=observed,
        ), consumer_observation)
    return _with_consumer(_result(
        "verified",
        "current_group_membership_matches",
        expected=expected,
        observed=observed,
    ), consumer_observation)


def _result(status: str, reason: str, **extra: Any) -> dict[str, Any]:
    result: dict[str, Any] = {
        "status": status,
        "scope": "current_state",
        "reason": reason,
        "consumer": {
            "status": "unsupported",
            "reason": "filter_consumption_unobserved",
        },
        "completion": {
            "status": "unknown",
            "reason": "group_reconfigure_not_correlated",
        },
    }
    result.update(extra)
    return result


def _unknown(reason: str, **extra: Any) -> dict[str, Any]:
    return _result("unknown", reason, **extra)


def _with_consumer(result: dict[str, Any], observation: Mapping[str, Any] | None) -> dict[str, Any]:
    """Fold a separate loaded-PF consumer observation into current status."""

    current_status = result["status"]
    result["current_status"] = current_status
    if observation is None:
        return result
    if not isinstance(observation, Mapping):
        result["consumer"] = {"status": "unknown", "reason": "malformed_consumer_observation"}
        if current_status == "verified":
            result["status"] = "unknown"
            result["reason"] = "malformed_consumer_observation"
        return result
    status = observation.get("status")
    if status not in {"verified", "not_applicable", "failed", "unknown", "incomplete", "unsupported"}:
        result["consumer"] = {"status": "unknown", "reason": "malformed_consumer_observation"}
        if current_status == "verified":
            result["status"] = "unknown"
            result["reason"] = "malformed_consumer_observation"
        return result
    result["consumer"] = dict(observation)
    if current_status != "verified":
        return result
    if status in {"verified", "not_applicable"}:
        return result
    result["status"] = status
    result["reason"] = observation.get("reason", "consumer_observation_unavailable")
    return result


def _overview_mapping(value: Any) -> tuple[dict[str, str] | None, str | None]:
    rows, complete, reason = _rows(value, "malformed_interface_overview")
    if rows is None:
        return None, reason
    if not complete:
        return None, "incomplete_interface_overview"

    mapping: dict[str, str] = {}
    physical_to_logical: dict[str, str] = {}
    for row in rows:
        if not isinstance(row, Mapping):
            return None, "malformed_interface_overview_row"
        logical = row.get("identifier")
        physical = _text(row.get("device"))
        if not isinstance(logical, str):
            return None, "malformed_interface_identifier"
        if physical is None:
            return None, "malformed_interface_device"
        # The overview also reports unassigned devices with identifier="";
        # they cannot map a desired logical member and are intentionally skipped.
        if logical == "":
            continue
        if logical in mapping:
            return None, "ambiguous_logical_interface_mapping"
        other_logical = physical_to_logical.get(physical)
        if other_logical is not None and other_logical != logical:
            return None, "ambiguous_physical_interface_mapping"
        mapping[logical] = physical
        physical_to_logical[physical] = logical
    return mapping, None


def _ifconfig_rows(value: Any) -> tuple[dict[str, dict[str, list[str]]] | None, str | None]:
    if not isinstance(value, Mapping) or not value:
        return None, "malformed_interface_diagnostics"
    result: dict[str, dict[str, list[str]]] = {}
    for raw_device, raw_details in value.items():
        device = _text(raw_device)
        if device is None or not isinstance(raw_details, Mapping):
            return None, "malformed_interface_diagnostics_row"
        groups = raw_details.get("groups")
        if isinstance(groups, (str, bytes, bytearray)) or not isinstance(groups, Sequence):
            return None, "interface_groups_unavailable"
        normalized: list[str] = []
        for group in groups:
            if not isinstance(group, str) or not group:
                return None, "malformed_interface_groups"
            normalized.append(group)
        if len(set(normalized)) != len(normalized):
            return None, "duplicate_interface_groups"
        result[device] = {"groups": normalized}
    return result, None


def _rows(value: Any, malformed_reason: str) -> tuple[list[Any] | None, bool, str | None]:
    if isinstance(value, (str, bytes, bytearray)):
        return None, False, malformed_reason
    if isinstance(value, Sequence):
        return list(value), True, None
    if not isinstance(value, Mapping):
        return None, False, malformed_reason
    raw_rows = value.get("rows")
    if isinstance(raw_rows, (str, bytes, bytearray)) or not isinstance(raw_rows, Sequence):
        return None, False, malformed_reason
    rows = list(raw_rows)
    current = value.get("current")
    row_count = value.get("rowCount")
    total = value.get("total")
    if type(current) is not int or current < 1 or type(row_count) is not int or row_count < 0:
        return None, False, malformed_reason
    if type(total) is not int or total < 0 or len(rows) > row_count or total < len(rows):
        return None, False, malformed_reason
    return rows, total == len(rows), None


def _member_list(value: Any) -> TypeGuard[Sequence[str]]:
    return (
        isinstance(value, Sequence)
        and not isinstance(value, (str, bytes, bytearray))
        and bool(value)
        and all(isinstance(item, str) and bool(item) for item in value)
    )


def _text(value: Any) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


__all__ = ["check_interface_group_current"]
