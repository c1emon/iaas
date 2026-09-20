"""Bounded current-state checks for an OPNsense gateway.

The inputs mirror the fixed 26.7.3 read paths:

* ``live_routes`` is the direct array returned by
  ``diagnostics/interface/get_routes``.
* ``gateway_status`` is the complete paginated response from
  ``routing/settings/search_gateway``.

This module deliberately reports current facts only.  It does not infer that
``routes configure`` completed, and it does not parse loaded ``route-to``
consumers.  The latter is an independent observation supplied by the PF rule
consumer checker when that evidence is available.
"""

from __future__ import annotations

from iaas_automation.common.conversion import optional_bool as _bool

from copy import deepcopy
from collections.abc import Mapping, Sequence
import ipaddress
from typing import Any


_VALID_STATUSES = {"verified", "failed", "unknown", "unsupported", "not_applicable"}


def _route_rows(value: Any) -> tuple[list[dict[str, Any]] | None, str | None]:
    """Validate the direct array returned by ``get_routes``."""

    if isinstance(value, (str, bytes, bytearray)) or not isinstance(value, Sequence):
        return None, "malformed_live_routes"
    rows = [deepcopy(dict(row)) for row in value if isinstance(row, Mapping)]
    if len(rows) != len(value):
        return None, "malformed_live_routes"
    return rows, None


def _gateway_rows(value: Any) -> tuple[list[dict[str, Any]] | None, str | None, bool]:
    """Validate one complete ``search_gateway`` page and its coverage.

    The boolean says whether the page is complete.  A missing gateway on an
    incomplete page is unknown rather than absent.
    """

    if not isinstance(value, Mapping) or not all(key in value for key in ("current", "rowCount", "total", "rows")):
        return None, "malformed_gateway_status", False
    current, row_count, total, raw_rows = (value["current"], value["rowCount"], value["total"], value["rows"])
    if (type(current) is not int or current < 1 or type(row_count) is not int or row_count < 0
            or type(total) is not int or total < 0 or isinstance(raw_rows, (str, bytes, bytearray))
            or not isinstance(raw_rows, Sequence)):
        return None, "malformed_gateway_status", False
    rows = [deepcopy(dict(row)) for row in raw_rows if isinstance(row, Mapping)]
    if len(rows) != len(raw_rows) or len(rows) > row_count or total < len(rows):
        return None, "malformed_gateway_status", False
    complete = total == len(rows) or total == 0
    return rows, None, complete



def _text(value: Any) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _destination_matches(expected: str, observed: Any) -> bool:
    observed_text = _text(observed)
    if observed_text is None:
        return False
    try:
        return ipaddress.ip_network(expected, strict=False) == ipaddress.ip_network(observed_text, strict=False)
    except ValueError:
        return expected == observed_text


def _fact(
    status: str,
    *,
    expected: Any = None,
    observed: Any = None,
    reason: str | None = None,
    scope: str | None = None,
) -> dict[str, Any]:
    result: dict[str, Any] = {"status": status, "expected": expected, "observed": observed}
    if reason is not None:
        result["reason"] = reason
    if scope is not None:
        result["scope"] = scope
    return result


def _find_gateway(rows: list[dict[str, Any]], name: str) -> dict[str, Any] | None:
    matches = [row for row in rows if row.get("name") == name]
    return matches[0] if len(matches) == 1 else None


def _configured_monitor(desired: Mapping[str, Any], live: Mapping[str, Any]) -> tuple[dict[str, Any], str]:
    # The desired document is only the expected value.  Falling back to it
    # would turn an absent live field into a false confirmation.
    expected_disabled = _bool(desired.get("monitor_disable"))
    expected_disabled = False if expected_disabled is None else expected_disabled
    disabled = _bool(live.get("monitor_disable"))
    monitor = _text(live.get("monitor"))
    if disabled is None:
        return _fact("unknown", expected={"enabled": not expected_disabled, "monitor": desired.get("monitor")},
                     observed={"monitor_disable": live.get("monitor_disable"), "monitor": live.get("monitor")},
                     reason="monitor_configuration_unavailable", scope="current_configuration"), "unknown"
    if expected_disabled:
        if disabled:
            return _fact("not_applicable", expected={"enabled": False, "monitor": None},
                         observed={"monitor_disable": disabled, "monitor": monitor},
                         reason="monitor_disabled_by_desired", scope="current_configuration"), "not_applicable"
        return _fact("failed", expected={"enabled": False, "monitor": None},
                     observed={"monitor_disable": disabled, "monitor": monitor},
                     reason="monitor_disable_mismatch", scope="current_configuration"), "failed"

    expected_monitor = _text(desired.get("monitor"))
    if "monitor" not in live:
        return _fact("unknown", expected={"enabled": True, "monitor": expected_monitor},
                     observed={"monitor_disable": disabled, "monitor": live.get("monitor")},
                     reason="monitor_configuration_unavailable", scope="current_configuration"), "unknown"
    if disabled or (expected_monitor is not None and monitor != expected_monitor):
        return _fact("failed", expected={"enabled": True, "monitor": expected_monitor},
                     observed={"monitor_disable": disabled, "monitor": monitor},
                     reason="monitor_not_enabled" if disabled else "monitor_target_mismatch",
                     scope="current_configuration"), "failed"
    return _fact("verified", expected={"enabled": True, "monitor": expected_monitor},
                 observed={"monitor_disable": disabled, "monitor": monitor,
                           "mode": "gateway_default" if monitor is None else "explicit"},
                 scope="current_configuration"), "verified"


def _route_check(
    expectation: Mapping[str, Any] | None,
    routes: list[dict[str, Any]],
    live: Mapping[str, Any],
) -> dict[str, Any]:
    if expectation is None:
        return _fact("not_applicable", reason="no_explicit_route_purpose")
    if not isinstance(expectation, Mapping):
        return _fact("unknown", reason="malformed_route_expectation")
    purpose = expectation.get("purpose")
    destination = _text(expectation.get("destination"))
    if purpose == "pbr_consumer":
        return _fact("unsupported", reason="route_to_consumer_requires_pf_rules")
    if purpose != "monitor_host" or destination is None:
        return _fact("unsupported", reason="route_purpose_unavailable")

    live_disable = _bool(live.get("monitor_disable"))
    live_noroute = _bool(live.get("monitor_noroute"))
    if live_disable is None or live_noroute is None:
        return _fact("unknown", expected={"monitor_disable": False, "monitor_noroute": False},
                     observed={"monitor_disable": live.get("monitor_disable"),
                               "monitor_noroute": live.get("monitor_noroute")},
                     reason="monitor_route_configuration_unavailable", scope="current_configuration")
    if live_disable or live_noroute:
        return _fact("not_applicable", expected={"monitor_disable": False, "monitor_noroute": False},
                     observed={"monitor_disable": live_disable, "monitor_noroute": live_noroute},
                     reason="monitor_host_route_not_required", scope="current_configuration")

    raw_if = _text(live.get("if"))
    live_gateway = _text(live.get("gateway"))
    if raw_if is None or live_gateway is None:
        return _fact("unknown", expected={"purpose": purpose, "destination": destination},
                     reason="route_interface_or_gateway_unavailable", scope="installed_route_snapshot")
    matches = [row for row in routes
               if _destination_matches(destination, row.get("destination"))
               and _text(row.get("gateway")) == live_gateway
               and _text(row.get("netif")) == raw_if]
    return _fact("verified" if matches else "failed",
                 expected={"purpose": purpose, "destination": destination,
                           "gateway": live_gateway, "netif": raw_if},
                 observed=matches if matches else routes,
                 reason=None if matches else "required_route_not_present",
                 scope="installed_route_snapshot")


def check_gateway_current(
    desired: Mapping[str, Any],
    live_routes: Any,
    gateway_status: Any,
    consumer_observation: Any | None = None,
    *,
    route_expectation: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Check one gateway's current interface, next hop, and monitor config.

    ``desired`` must identify the gateway by ``name`` and provide its logical
    ``interface`` and native ``gateway`` address.  A route is checked only
    when an explicit ``route_expectation`` purpose is supplied; an arbitrary
    route through the next hop is never treated as required.  The function
    never maps logical interface names to route interfaces by position or by
    list order.
    """

    if not isinstance(desired, Mapping):
        return {"status": "unknown", "reason": "malformed_desired_gateway"}
    name = _text(desired.get("name"))
    expected_logical = _text(desired.get("interface"))
    expected_gateway = _text(desired.get("gateway"))
    if name is None or expected_logical is None or expected_gateway is None:
        return {"status": "unknown", "reason": "required_gateway_identity_unavailable"}

    if route_expectation is None or live_routes is None:
        routes, route_error = [], None
    else:
        parsed_routes, route_error = _route_rows(live_routes)
        routes = parsed_routes if parsed_routes is not None else []
    statuses, status_error, status_complete = _gateway_rows(gateway_status)
    if statuses is None:
        return {"status": "unknown", "reason": status_error, "completion": _completion()}

    if not status_complete:
        return {"status": "unknown", "reason": "gateway_status_page_incomplete", "completion": _completion()}

    live = _find_gateway(statuses, name)
    if live is None:
        reason = "gateway_status_page_incomplete" if not status_complete else "gateway_status_missing_or_ambiguous"
        return {"status": "unknown", "reason": reason, "completion": _completion()}

    observed_logical = _text(live.get("interface"))
    interface = _fact(
        "verified" if observed_logical == expected_logical else "failed" if observed_logical else "unknown",
        expected=expected_logical,
        observed=observed_logical,
        reason=None if observed_logical else "gateway_interface_unavailable",
        scope="current_configuration",
    )
    observed_physical = _text(live.get("if"))
    physical_interface = _fact(
        "verified" if observed_physical else "unknown",
        observed=observed_physical,
        reason=None if observed_physical else "gateway_physical_interface_unavailable",
        scope="current_interface_mapping",
    )

    observed_gateway = _text(live.get("gateway"))
    next_hop = _fact(
        "verified" if observed_gateway == expected_gateway else "failed" if observed_gateway else "unknown",
        expected=expected_gateway,
        observed=observed_gateway,
        reason=None if observed_gateway == expected_gateway else
        "gateway_next_hop_mismatch" if observed_gateway else "gateway_next_hop_unavailable",
        scope="current_configuration",
    )

    monitor, monitor_state = _configured_monitor(desired, live)
    route = _route_check(route_expectation, routes, live)
    if route_error is not None and route["status"] in {"verified", "failed"}:
        route = _fact("unknown", reason=route_error, scope="installed_route_snapshot")
    runtime_status = _fact(
        "not_applicable" if _text(live.get("status")) is not None else "unknown",
        observed=live.get("status"),
        reason="runtime_status_informational_only" if _text(live.get("status")) is not None
        else "gateway_runtime_status_unavailable",
        scope="runtime_observation",
    )

    checks = {"interface": interface, "physical_interface": physical_interface, "next_hop": next_hop,
              "monitor_configuration": monitor, "runtime_status": runtime_status,
              "route": route}
    required = [interface["status"], next_hop["status"], monitor_state, route["status"]]
    current_status = _aggregate(required)
    consumer = _consumer(consumer_observation)
    status = _aggregate([current_status, consumer["status"]], consumer=True)
    return {
        "status": status,
        "current_status": current_status,
        "identity": name,
        "checks": checks,
        "consumer": consumer,
        "completion": _completion(),
    }


def _aggregate(statuses: Sequence[str], *, consumer: bool = False) -> str:
    if "failed" in statuses:
        return "failed"
    if "unknown" in statuses:
        return "unknown"
    if "unsupported" in statuses:
        return "unsupported" if consumer else "unsupported"
    return "verified" if all(status in {"verified", "not_applicable"} for status in statuses) else "unknown"


def _consumer(value: Any) -> dict[str, Any]:
    if value is None:
        return {"status": "unsupported", "reason": "loaded_route_to_observation_unavailable"}
    if not isinstance(value, Mapping):
        return {"status": "unknown", "reason": "malformed_consumer_observation"}
    status = value.get("status")
    if status not in _VALID_STATUSES:
        return {"status": "unknown", "reason": "malformed_consumer_observation"}
    return deepcopy(dict(value))


def _completion() -> dict[str, Any]:
    return {"status": "unknown", "reason": "gateway_reconfigure_not_correlated"}


__all__ = ["check_gateway_current"]
