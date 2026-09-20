"""Bounded, read-only OPNsense configuration observations.

The workflow deliberately keeps the provider boundary small.  ``Reader`` only
knows how to ask a fixed Collection client for one of the seven supported list
targets; the client is injected by the launcher.  This makes the adapter easy
to exercise with representative responses and prevents a request from turning
into an arbitrary API or command runner.
"""

from __future__ import annotations

from copy import deepcopy
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from decimal import Decimal
import ipaddress
import json
import re
import time
from typing import Any, Callable, Iterator, Protocol
from urllib.parse import urlsplit

import requests
from urllib3.util import Timeout

from iaas_automation.opnsense_diagnostics.schema import ALIAS_NAME
from iaas_automation.opnsense_validation import TOP_LEVEL, validate_document
from iaas_automation.common.errors import ValidationError
from .gateway_checks import check_gateway_current


MAX_PAGE_ROWS = 1000
MAX_PAGES = 5
MAX_RESPONSE_BYTES = 2 * 1024 * 1024
MAX_TOTAL_BYTES = 8 * 1024 * 1024

SUPPORTED_RESOURCES = (
    "aliases",
    "vips",
    "gateways",
    "filter-rules",
    "dnat",
    "one-to-one-nat",
    "interface-groups",
)

# These are the exact list targets exposed by oxlorg.opnsense 26.1.11.  They
# are intentionally constants: callers cannot supply a module, controller, or
# endpoint of their own.
COLLECTION_TARGETS = {
    "aliases": "alias",
    "vips": "interface_vip",
    "gateways": "gateway",
    "filter-rules": "rule",
    "dnat": "nat_destination",
    "one-to-one-nat": "nat_one_to_one",
    "interface-groups": "rule_interface_group",
}

_COLLECTION_GET = {
    "alias": ("firewall", "alias", "alias.aliases.alias"),
    "interface_vip": ("interfaces", "vip_settings", "vip.vip"),
    "rule": ("firewall", "filter", "filter.rules.rule"),
    "nat_destination": ("firewall", "d_nat", "DNat.rule"),
    "nat_one_to_one": ("firewall", "one_to_one", "filter.onetoone.rule"),
    "rule_interface_group": ("firewall", "group", "group.ifgroupentry"),
}


class _HttpFailure(RuntimeError):
    def __init__(self, status: str, reason: str):
        super().__init__(reason)
        self.status = status
        self.reason = reason


@dataclass(frozen=True)
class ObservationBudget:
    """Monotonic deadline shared by all reads in one confirmation boundary."""

    deadline: float
    clock: Callable[[], float] = time.monotonic
    request_timeout_seconds: float = 15.0

    def remaining(self) -> float:
        return max(0.0, self.deadline - self.clock())

    def timeout(self, requested: float | None = None) -> float:
        remaining = self.remaining()
        if remaining <= 0:
            raise TimeoutError("observation deadline exhausted")
        return remaining if requested is None else min(requested, remaining)


_OBSERVATION_BUDGET: ContextVar[ObservationBudget | None] = ContextVar(
    "iaas_opnsense_observation_budget", default=None
)


@contextmanager
def observation_budget(seconds: float, *, clock: Callable[[], float] = time.monotonic,
                       request_timeout_seconds: float = 15.0) -> Iterator[ObservationBudget]:
    """Install one cooperative read deadline for nested fixed-transport calls."""

    if isinstance(seconds, bool) or not isinstance(seconds, (int, float)) or seconds <= 0:
        raise ValueError("observation budget must be greater than zero")
    if (isinstance(request_timeout_seconds, bool) or not isinstance(request_timeout_seconds, (int, float))
            or not 0 < request_timeout_seconds <= 15):
        raise ValueError("request timeout must be within the fixed limit")
    budget = ObservationBudget(clock() + float(seconds), clock, float(request_timeout_seconds))
    token = _OBSERVATION_BUDGET.set(budget)
    try:
        yield budget
    finally:
        _OBSERVATION_BUDGET.reset(token)


def current_observation_budget() -> ObservationBudget | None:
    """Return the current cooperative budget for a fixed transport call."""

    return _OBSERVATION_BUDGET.get()


class ReadTransport(Protocol):
    """The read-only part of the fixed Collection client.

    ``list`` may return a complete list (the Collection's ``list`` module
    shape) or one bounded page with ``rows``, ``current`` and ``total``.  A
    launcher can implement this protocol around the already loaded Ansible
    Collection without exposing arbitrary API calls here.
    """

    def list(self, target: str, **kwargs: Any) -> Any:
        ...


class UnsupportedRead(RuntimeError):
    """Raised when the fixed client cannot provide a selected list target."""


class FixedCollectionTransport:
    """Bounded HTTP wrapper for the pinned Collection's read-only list paths.

    The paths and response containers mirror ``oxlorg.opnsense`` 26.1.11's
    ``list`` module and resource models.  There is no method accepting a
    caller-supplied endpoint, command, or request body; only the fixed list and
    model-detail calls below are reachable.  A launcher may still inject its
    loaded Collection client through ``Reader(..., transport=...)``.
    """

    def __init__(self, target: dict[str, Any], credentials: dict[str, Any], session: Any | None = None):
        self.target = deepcopy(target)
        self._credential_names = tuple(sorted(str(key) for key in credentials))
        self._used = 0
        self._session = session if session is not None else requests.Session()
        key = credentials.get("OPNSENSE_API_KEY")
        secret = credentials.get("OPNSENSE_API_SECRET")
        if isinstance(key, str) and isinstance(secret, str) and key and secret:
            self._session.auth = (key, secret)
        self._session.verify = target["ssl_verify"]
        self._base = target["endpoint"].rstrip("/") + "/api/"

    def close(self) -> None:
        close = getattr(self._session, "close", None)
        if callable(close):
            close()

    def _request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> Any:
        if not (path.startswith("firewall/") or path.startswith("interfaces/")
                or path.startswith("routing/") or path.startswith("diagnostics/")
                or (method == "GET" and path == "core/firmware/status")):
            raise UnsupportedRead("fixed_collection_path_rejected")
        if "OPNSENSE_API_KEY" not in self._credential_names or "OPNSENSE_API_SECRET" not in self._credential_names:
            raise UnsupportedRead("OPNSENSE_API_credentials_missing")
        budget = current_observation_budget()
        if budget is not None and budget.remaining() <= 0:
            raise _HttpFailure("failed", "observation_deadline_exhausted")
        try:
            remaining = None if budget is None else min(budget.remaining(), budget.request_timeout_seconds)
            if remaining is not None and remaining <= 0:
                raise _HttpFailure("failed", "observation_deadline_exhausted")
            request_timeout = (5, 15) if remaining is None else Timeout(
                total=remaining, connect=min(5.0, remaining), read=min(15.0, remaining))
            kwargs = {"verify": self.target["ssl_verify"], "timeout": request_timeout, "allow_redirects": False,
                      "stream": True}
            if method == "POST":
                kwargs["json"] = payload or {}
            response = self._session.request(method, self._base + path, **kwargs)
        except requests.Timeout as error:
            raise _HttpFailure("failed", "timeout") from error
        except requests.RequestException as error:
            raise _HttpFailure("failed", "transport_failure") from error
        if budget is not None and budget.remaining() <= 0:
            close = getattr(response, "close", None)
            if callable(close):
                close()
            raise _HttpFailure("failed", "observation_deadline_exhausted")
        if response.status_code in (404, 405, 501):
            raise _HttpFailure("unsupported", "endpoint_unavailable")
        if response.status_code == 401:
            raise _HttpFailure("failed", "authentication_failed")
        if response.status_code == 403:
            raise _HttpFailure("failed", "permission_denied")
        if not 200 <= response.status_code < 300:
            raise _HttpFailure("failed", "http_failure")
        body = bytearray()
        try:
            chunks = response.iter_content(8192) if callable(getattr(response, "iter_content", None)) else [response.content]
            for chunk in chunks:
                if budget is not None and budget.remaining() <= 0:
                    raise _HttpFailure("failed", "observation_deadline_exhausted")
                if not isinstance(chunk, (bytes, bytearray)):
                    raise _HttpFailure("failed", "malformed_response_body")
                body.extend(chunk)
                self._used += len(chunk)
                if len(body) > MAX_RESPONSE_BYTES or self._used > MAX_TOTAL_BYTES:
                    raise _HttpFailure("unsupported", "response_bound_exceeded")
            if budget is not None and budget.remaining() <= 0:
                raise _HttpFailure("failed", "observation_deadline_exhausted")
            return json.loads(bytes(body), parse_constant=lambda _: (_ for _ in ()).throw(ValueError("invalid_json")))
        except _HttpFailure:
            raise
        except (ValueError, UnicodeError) as error:
            raise _HttpFailure("failed", "malformed_json") from error
        finally:
            close = getattr(response, "close", None)
            if callable(close):
                close()

    @staticmethod
    def _path(value: Any, path: str) -> Any:
        for part in path.split("."):
            if not isinstance(value, dict) or part not in value:
                raise _HttpFailure("unsupported", "collection_response_shape_unavailable")
            value = value[part]
        return value

    @classmethod
    def _entries(cls, response: Any, path: str) -> list[dict[str, Any]]:
        data = cls._path(response, path)
        if isinstance(data, dict):
            if not data:
                return []
            if all(not isinstance(value, (dict, list)) for value in data.values()):
                return [deepcopy(data)]
            entries = []
            for uuid, value in data.items():
                if not isinstance(value, dict):
                    raise _HttpFailure("failed", "malformed_collection_entry")
                entry = deepcopy(value)
                entry.setdefault("uuid", uuid)
                entries.append(entry)
            return entries
        if isinstance(data, list) and all(isinstance(value, dict) for value in data):
            return deepcopy(data)
        raise _HttpFailure("failed", "malformed_collection_entry")

    @staticmethod
    def _provider_row(row: dict[str, Any]) -> dict[str, Any]:
        result = deepcopy(row)
        # These four fields are inverted by simplify_translate in the pinned
        # Collection.  Apply that same conversion to raw API fixture/results.
        for raw, canonical in (("disabled", "enabled"), ("nobind", "bind"),
                               ("noexpand", "expand"), ("nogroup", "gui_group")):
            if canonical not in result and raw in result:
                value = _coerce_bool(result[raw])
                result[canonical] = not value if type(value) is bool else value
        if "updatefreq" in result and "updatefreq_days" not in result:
            result["updatefreq_days"] = result["updatefreq"]
        return result

    def list(self, target: str, **kwargs: Any) -> Any:
        page = kwargs.get("page", 1)
        page_size = kwargs.get("page_size", MAX_PAGE_ROWS)
        if type(page) is not int or page < 1 or page > MAX_PAGES or type(page_size) is not int or page_size != MAX_PAGE_ROWS:
            raise UnsupportedRead("invalid_collection_page_request")
        if target == "gateway":
            response = self._request("POST", "routing/settings/search_gateway",
                                     {"current": page, "rowCount": page_size})
            if (not isinstance(response, dict) or not isinstance(response.get("rows"), list)
                    or response.get("current") != page or type(response.get("rowCount")) is not int
                    or type(response.get("total")) is not int or response["total"] < 0
                    or response["rowCount"] < 0):
                raise _HttpFailure("failed", "malformed_gateway_page")
            rows = []
            for row in response["rows"]:
                if not isinstance(row, dict):
                    raise _HttpFailure("failed", "malformed_gateway_page")
                uuid = row.get("uuid", row.get("id"))
                if isinstance(uuid, str) and uuid:
                    detail = self._request("GET", f"routing/settings/get_gateway/{uuid}")
                    item = self._path(detail, "gateway_item")
                    if not isinstance(item, dict) or not item:
                        raise _HttpFailure("failed", "malformed_gateway_detail")
                    row = deepcopy(item)
                    row.setdefault("uuid", uuid)
                else:
                    raise _HttpFailure("failed", "missing_gateway_detail_identity")
                rows.append(self._provider_row(row))
            return {"current": response["current"], "rowCount": response["rowCount"],
                    "total": response["total"], "rows": rows}
        try:
            module, controller, response_path = _COLLECTION_GET[target]
        except KeyError as error:
            raise UnsupportedRead("unsupported_collection_target") from error
        response = self._request("GET", f"{module}/{controller}/get")
        return [self._provider_row(row) for row in self._entries(response, response_path)]

    def confirmation_capabilities(self) -> dict[str, Any]:
        """Fixed source-audited profile; a controller ack is not completion."""
        from .confirmation import SYNC_RESOURCES
        try:
            response = self._request("GET", "core/firmware/status")
            product = response.get("product", {}) if isinstance(response, dict) else {}
            version = product.get("product_version") if isinstance(product, dict) else None
        except (UnsupportedRead, _HttpFailure):
            version = None
        profiles = {}
        for resource in SUPPORTED_RESOURCES:
            supported = version == "26.7.3" and resource in SYNC_RESOURCES
            profiles[resource] = {
                "activation_completion": "available" if supported else "unknown" if version != "26.7.3" else "unsupported",
                "source_processing": "unsupported", "content_loading": "unsupported",
                "basis": "OPNsense 26.7.3 / fixed Collection 1423500c29f88da9ba8147a23fc64006cf464159",
                "device_version": "26.7.3" if version == "26.7.3" else None,
                "reason": "device_version_unqualified" if version != "26.7.3" else
                          "synchronous_configd_return" if supported else "native_action_completion_unavailable",
            }
        return profiles

    def interfaces(self) -> list[str]:
        """Group member choices expose logical interface keys, excluding groups.

        OPNsense Firewall/FieldTypes/InterfaceField explicitly skips type=group.
        Diagnostics get_interface_names instead exposes raw NIC names (igb0).
        """
        response = self._request("GET", "firewall/group/get_item")
        choices = self._path(response, 'group.members')
        if not isinstance(choices, dict) or any(not isinstance(name, str) or not name
                                               or not isinstance(value, dict) for name, value in choices.items()):
            raise _HttpFailure('failed', 'malformed_interface_choices')
        return sorted(choices)

    def active_check(
        self,
        resource: str,
        identity: list[str],
        desired: dict[str, Any],
        *,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Use the restricted diagnostics alias-table read when it can prove activity."""
        if resource == "gateways":
            return self._gateway_active_observation(identity, desired, context)
        if resource == "interface-groups":
            return self._group_current_observation(identity, desired, context)
        if resource != "aliases" or len(identity) != 1 or not isinstance(identity[0], str) \
                or not ALIAS_NAME.fullmatch(identity[0]):
            return {"status": "unsupported", "reason": "active_observation_unavailable",
                    "coverage": "saved_configuration_only"}
        alias = identity[0]
        alias_type = desired.get("type") if isinstance(desired, dict) else None
        state = desired.get("state") if isinstance(desired, dict) else None
        if state != "present" or desired.get("enabled") is not True:
            return self._retired_alias_observation(alias)
        if alias_type == "port":
            return self._port_alias_observation(desired)
        try:
            response = self._request("POST", f"firewall/alias_util/list/{alias}",
                                     {"rowCount": MAX_PAGE_ROWS, "current": 1})
        except _HttpFailure as error:
            return {"status": "unsupported" if error.status == "unsupported" else "unknown", "reason": error.reason,
                    "coverage": "alias_table_unavailable"}
        if isinstance(response, dict) and isinstance(response.get("rows"), list):
            rows = response["rows"]
            total = response.get("total")
        elif isinstance(response, list):
            rows, total = response, len(response)
        else:
            return {"status": "incomplete", "reason": "malformed_alias_table", "coverage": "alias_table"}
        if type(total) is not int or total != len(rows) or len(rows) > MAX_PAGE_ROWS:
            return {"status": "incomplete", "reason": "malformed_alias_table", "coverage": "alias_table"}
        coverage = {"scope": "alias_table", "rows": len(rows), "total": total,
                    "membership_observed": True}
        if alias_type in {"urltable", "urljson", "dynipv6host"}:
            return {"status": "unsupported", "reason": "dynamic_alias_membership_not_refresh_proof",
                    "coverage": coverage}
        if alias_type == "networkgroup":
            expected, dependency_status, dependency_reason, dependency_coverage = self._networkgroup_members(
                alias, desired, context
            )
            coverage["dependency"] = dependency_coverage
            if dependency_status != "verified":
                return {"status": dependency_status, "reason": dependency_reason,
                        "coverage": coverage}
        elif alias_type in {"host", "network"}:
            expected, dependency_status, dependency_reason = self._static_members(desired)
            coverage["dependency"] = {"scope": "selected_definition", "status": dependency_status}
            if dependency_status != "verified":
                return {"status": dependency_status, "reason": dependency_reason,
                        "coverage": coverage}
        else:
            return {"status": "unsupported", "reason": "alias_type_active_proof_unavailable",
                    "coverage": coverage}
        observed_values: list[str] = []
        for row in rows:
            if not isinstance(row, dict) or not isinstance(row.get("ip"), str):
                return {"status": "incomplete", "reason": "malformed_alias_table",
                        "coverage": coverage}
            observed_values.append(row["ip"])
        observed, observed_status = self._canonical_networks(observed_values)
        if observed_status != "verified":
            return {"status": "incomplete", "reason": "malformed_alias_table_entry",
                    "coverage": coverage}
        coverage["expected"] = len(expected)
        coverage["matched"] = len(observed & expected)
        if observed == expected:
            return {"status": "verified", "reason": None, "coverage": coverage}
        return {"status": "failed", "reason": "alias_table_membership_mismatch", "coverage": coverage}

    def _port_alias_observation(self, desired: dict[str, Any]) -> dict[str, Any]:
        from .pf_rules import PF_STATISTICS_RULES_PATH, check_port_alias_active
        if self.confirmation_capabilities()["aliases"]["device_version"] != "26.7.3":
            return {"status": "unsupported", "reason": "device_version_unqualified"}
        consumers = []
        try:
            for resource in ("filter-rules", "dnat", "one-to-one-nat"):
                rows = self.list(COLLECTION_TARGETS[resource])
                if not isinstance(rows, list) or len(rows) > MAX_PAGE_ROWS * MAX_PAGES:
                    return {"status": "incomplete", "reason": "port_consumer_configuration_incomplete"}
                for row in rows:
                    if not isinstance(row, dict):
                        return {"status": "incomplete", "reason": "port_consumer_configuration_malformed"}
                    config = _flatten_provider_row(row, resource)
                    config["resource"] = resource
                    consumers.append(config)
            snapshot = self._request("GET", PF_STATISTICS_RULES_PATH)
        except _HttpFailure as error:
            return {"status": "unsupported" if error.status == "unsupported" else "unknown",
                    "reason": error.reason, "coverage": "loaded_port_rules"}
        return check_port_alias_active(desired, snapshot, consumers)

    def _gateway_active_observation(
        self,
        identity: list[str],
        desired: dict[str, Any],
        context: dict[str, Any] | None,
    ) -> dict[str, Any]:
        """Observe one gateway through the fixed 26.7.3 native read paths.

        ``search_gateway`` is fetched directly so its runtime fields are
        retained.  Pagination is bounded and must be complete before the
        selected row can be associated.  A route table is requested only for
        an explicit monitor-host route expectation whose live configuration
        says that such a route is required.
        """
        coverage: dict[str, Any] = {
            "scope": "gateway_current",
            "source": "OPNsense 26.7.3",
            "gateway_status": {"pages": 0, "rows": 0, "total": None, "complete": False},
            "routes": "not_requested",
        }
        try:
            firmware = self._request("GET", "core/firmware/status")
        except _HttpFailure as error:
            return {"status": "unsupported" if error.status == "unsupported" else "unknown",
                    "reason": error.reason, "coverage": coverage}
        product = firmware.get("product") if isinstance(firmware, dict) else None
        version = product.get("product_version") if isinstance(product, dict) else None
        coverage["device_version"] = version
        if not isinstance(version, str) or not version:
            return {"status": "unknown", "reason": "device_version_unavailable", "coverage": coverage}
        if version != "26.7.3":
            return {"status": "unsupported", "reason": "device_version_unqualified", "coverage": coverage}

        if (not isinstance(identity, list) or len(identity) != 2
                or any(not isinstance(value, str) or not value for value in identity)
                or not isinstance(desired, dict)):
            return {"status": "unsupported", "reason": "gateway_identity_unavailable", "coverage": coverage}
        if desired.get("name") != identity[0] or desired.get("gateway") != identity[1]:
            return {"status": "unsupported", "reason": "gateway_identity_mismatch", "coverage": coverage}

        rows: list[dict[str, Any]] = []
        total: int | None = None
        try:
            for page in range(1, MAX_PAGES + 1):
                response = self._request("POST", "routing/settings/search_gateway",
                                         {"current": page, "rowCount": MAX_PAGE_ROWS})
                if (not isinstance(response, dict)
                        or response.get("current") != page
                        or type(response.get("rowCount")) is not int
                        or response["rowCount"] < 0
                        or type(response.get("total")) is not int
                        or response["total"] < 0
                        or not isinstance(response.get("rows"), list)
                        or len(response["rows"]) > response["rowCount"]
                        or any(not isinstance(row, dict) for row in response["rows"])):
                    return {"status": "unknown", "reason": "malformed_gateway_page", "coverage": coverage}
                page_total = response["total"]
                if total is None:
                    total = page_total
                elif page_total != total:
                    return {"status": "unknown", "reason": "gateway_status_total_changed", "coverage": coverage}
                rows.extend(deepcopy(response["rows"]))
                coverage["gateway_status"].update({"pages": page, "rows": len(rows), "total": total})
                if total == len(rows):
                    coverage["gateway_status"]["complete"] = True
                    break
            if not coverage["gateway_status"]["complete"]:
                reason = ("gateway_configuration_bound_exceeded"
                          if (total is not None and total > MAX_PAGE_ROWS * MAX_PAGES)
                          else "gateway_configuration_incomplete")
                return {"status": "unknown", "reason": reason, "coverage": coverage}

            selected_rows = [row for row in rows if row.get("name") == identity[0]]
            selected_live = selected_rows[0] if len(selected_rows) == 1 else None

            # Gateway active evidence is collected here from fixed native read
            # paths.  Caller context cannot replace the PF consumer proof.
            from .pf_consumers import check_gateway_active
            from .pf_rules import PF_STATISTICS_RULES_PATH

            consumers_raw = self.list("rule")
            if (not isinstance(consumers_raw, list)
                    or len(consumers_raw) > MAX_PAGE_ROWS * MAX_PAGES
                    or any(not isinstance(row, dict) for row in consumers_raw)):
                return {"status": "unknown", "reason": "filter_consumer_configuration_incomplete",
                        "coverage": coverage}
            consumers = []
            for row in consumers_raw:
                consumer = _flatten_provider_row(row, "filter-rules")
                consumer["resource"] = "filter-rules"
                consumers.append(consumer)
            pf_snapshot = self._request("GET", PF_STATISTICS_RULES_PATH)
            physical = selected_live.get("if") if isinstance(selected_live, dict) else None
            gateway_for_pf = deepcopy(desired)
            gateway_for_pf["physical_interfaces"] = [physical] if isinstance(physical, str) and physical else None
            consumer_observation = check_gateway_active(gateway_for_pf, pf_snapshot, consumers)

            route_expectation = None
            monitor = desired.get("monitor")
            if (isinstance(monitor, str) and monitor.strip()
                    and desired.get("monitor_disable") is False
                    and desired.get("monitor_noroute") is False
                    and monitor.strip() != desired.get("gateway")):
                try:
                    monitor_address = ipaddress.ip_address(monitor.strip())
                    destination = f"{monitor_address}/{monitor_address.max_prefixlen}"
                except ValueError:
                    destination = monitor.strip()
                route_expectation = {"purpose": "monitor_host", "destination": destination}
            live_routes: Any = None
            explicit_monitor_route = (isinstance(route_expectation, dict)
                                      and route_expectation.get("purpose") == "monitor_host")
            native_false = {False, 0, "0", "false", "False", "no", "No"}
            route_required = (isinstance(selected_live, dict)
                              and selected_live.get("monitor_disable") in native_false
                              and selected_live.get("monitor_noroute") in native_false)
            if explicit_monitor_route and route_required:
                live_routes = self._request("GET", "diagnostics/interface/get_routes")
                coverage["routes"] = "requested"
                if not isinstance(live_routes, list):
                    return {"status": "unknown", "reason": "malformed_live_routes", "coverage": coverage}
            elif explicit_monitor_route:
                coverage["routes"] = "not_required_by_configuration"

            status_page = {"current": 1, "rowCount": max(MAX_PAGE_ROWS, len(rows)),
                           "total": len(rows), "rows": rows}
            result = check_gateway_current(
                desired, live_routes, status_page, consumer_observation,
                route_expectation=route_expectation,
            )
            result["coverage"] = coverage
            return result
        except _HttpFailure as error:
            return {"status": "unsupported" if error.status == "unsupported" else "unknown",
                    "reason": error.reason, "coverage": coverage}

    def _retired_alias_observation(self, alias: str) -> dict[str, Any]:
        """Record retirement observations without inventing a cleanup guarantee."""
        coverage: dict[str, Any] = {"scope": "alias_retirement", "table": "unknown",
                                    "consumers": "unobserved", "pf_states": "not_touched"}
        try:
            tables = self._request("GET", "firewall/alias_util/aliases")
            if not isinstance(tables, list) or any(not isinstance(name, str) or not name for name in tables):
                return {"status": "unknown", "reason": "table_enumeration_unavailable", "coverage": coverage}
            coverage["table"] = "absent" if alias not in tables else "residual"
            if alias in tables:
                response = self._request("POST", f"firewall/alias_util/list/{alias}",
                                         {"rowCount": MAX_PAGE_ROWS, "current": 1})
                if not isinstance(response, dict) or not isinstance(response.get("rows"), list):
                    return {"status": "unknown", "reason": "table_members_unavailable", "coverage": coverage}
                rows = response["rows"]
                if type(response.get("total")) is not int or response["total"] != len(rows) or len(rows) > MAX_PAGE_ROWS:
                    return {"status": "incomplete", "reason": "table_members_incomplete", "coverage": coverage}
                if any(not isinstance(row, dict) or not isinstance(row.get("ip"), str) for row in rows):
                    return {"status": "incomplete", "reason": "table_members_malformed", "coverage": coverage}
                coverage["observed_rows"] = len(rows)
                # listAction maps backend null/error to an empty recordset.  An
                # empty response alone cannot prove an empty native PF table.
                coverage["table"] = "residual_nonempty" if rows else "empty_or_unreadable"
        except _HttpFailure as error:
            return {"status": "unsupported" if error.status == "unsupported" else "unknown",
                    "reason": error.reason, "coverage": coverage}
        return {"status": "unsupported", "reason": "native_retirement_and_consumers_unconfirmed",
                "coverage": coverage}

    def _group_current_observation(
        self,
        identity: list[str],
        desired: dict[str, Any],
        context: dict[str, Any] | None,
    ) -> dict[str, Any]:
        """Check saved group members against current ifconfig membership.

        The version gate, interface reads, complete filter/NAT consumer reads,
        and loaded PF snapshot are all fixed.  ``context`` never substitutes
        for these observations; operation completion remains a separate
        unknown fact.
        """
        from .group_checks import check_interface_group_current
        from .pf_consumers import check_interface_group_active
        from .pf_rules import PF_STATISTICS_RULES_PATH

        if (len(identity) != 1 or not isinstance(identity[0], str) or not identity[0]
                or not isinstance(desired, dict)):
            return {"status": "unknown", "reason": "malformed_interface_group_identity"}
        if desired.get("name") not in (None, identity[0]):
            return {"status": "unknown", "reason": "interface_group_identity_mismatch"}
        if desired.get("name") is None:
            desired = {**desired, "name": identity[0]}

        try:
            version_response = self._request("GET", "core/firmware/status")
        except _HttpFailure as error:
            return self._group_observation_failure(error)
        product = version_response.get("product") if isinstance(version_response, dict) else None
        version = product.get("product_version") if isinstance(product, dict) else None
        if not isinstance(version, str) or not version:
            return {"status": "unknown", "reason": "device_version_unavailable"}
        if version != "26.7.3":
            return {"status": "unsupported", "reason": "device_version_unqualified",
                    "device_version": version}

        try:
            overview = self._request("GET", "interfaces/overview/interfaces_info")
            ifconfig = self._request("GET", "diagnostics/interface/get_interface_config")
        except _HttpFailure as error:
            return self._group_observation_failure(error)

        result = check_interface_group_current(desired, overview, ifconfig)
        if result.get("status") != "verified":
            result["device_version"] = version
            return result

        expected = result.get("expected")
        physical_members = expected.get("physical_members") if isinstance(expected, dict) else None
        if not isinstance(physical_members, list) or any(not isinstance(item, str) for item in physical_members):
            result["device_version"] = version
            return result
        try:
            consumers = []
            for resource in ("filter-rules", "dnat", "one-to-one-nat"):
                rows = self.list(COLLECTION_TARGETS[resource])
                if (not isinstance(rows, list) or len(rows) > MAX_PAGE_ROWS * MAX_PAGES
                        or any(not isinstance(row, dict) for row in rows)):
                    consumer = {"status": "incomplete", "reason": "malformed_consumer_configuration"}
                    break
                for row in rows:
                    consumer_row = _flatten_provider_row(row, resource)
                    consumer_row["resource"] = resource
                    consumers.append(consumer_row)
            else:
                snapshot = self._request("GET", PF_STATISTICS_RULES_PATH)
                consumer = check_interface_group_active(
                    {"name": identity[0], "members": physical_members},
                    snapshot,
                    consumers,
                )
        except UnsupportedRead as error:
            consumer = {"status": "unsupported", "reason": str(error)}
        except _HttpFailure as error:
            consumer = {"status": "unsupported" if error.status == "unsupported" else "unknown",
                        "reason": error.reason}
        result = check_interface_group_current(desired, overview, ifconfig, consumer)
        result["device_version"] = version
        return result

    @staticmethod
    def _group_observation_failure(error: _HttpFailure) -> dict[str, Any]:
        if error.status == "unsupported":
            return {"status": "unsupported", "reason": error.reason}
        return {"status": "unknown", "reason": error.reason}

    @staticmethod
    def _static_members(desired: dict[str, Any]) -> tuple[set[str], str, str | None]:
        expected_values = desired.get("content") if isinstance(desired, dict) else None
        if not isinstance(expected_values, list) or not expected_values:
            return set(), "unsupported", "static_alias_membership_unavailable"
        expected_values = [value for value in expected_values if isinstance(value, str)]
        if len(expected_values) != len(desired.get("content", [])):
            return set(), "unsupported", "static_alias_membership_unavailable"
        expected, status = FixedCollectionTransport._canonical_networks(expected_values)
        if status != "verified":
            return set(), "unsupported", "static_alias_membership_unavailable"
        return expected, "verified", None

    @staticmethod
    def _canonical_networks(values: list[str]) -> tuple[set[str], str]:
        parsed: dict[int, list[Any]] = {4: [], 6: []}
        for value in values:
            try:
                network = ipaddress.ip_network(value, strict=False)
            except ValueError:
                return set(), "failed"
            parsed[network.version].append(network)
        return {str(network) for version in (4, 6) for network in ipaddress.collapse_addresses(parsed[version])}, "verified"

    @staticmethod
    def _is_network_literal(value: str) -> bool:
        try:
            ipaddress.ip_network(value, strict=False)
        except ValueError:
            return False
        return True

    def _networkgroup_members(
        self,
        alias: str,
        desired: dict[str, Any],
        context: dict[str, Any] | None,
    ) -> tuple[set[str], str, str | None, dict[str, Any]]:
        """Resolve a static group from selected transitions and live dependencies.

        The selected declaration wins only for selected aliases.  Every other
        member is read from the appliance (or from an explicitly supplied live
        observation).  Dynamic, missing, malformed, and incomplete members
        never become an empty set, because that could turn an unreadable group
        into a false active confirmation.
        """
        content = desired.get("content") if isinstance(desired, dict) else None
        literal_only = isinstance(content, list) and bool(content) and all(
            isinstance(value, str) and self._is_network_literal(value) for value in content
        )
        selected, live, live_status = self._networkgroup_definitions(context, require_live=not literal_only)
        selected[alias] = deepcopy(desired)
        dependency_coverage = {
            "scope": "selected_transitions_and_live_dependencies",
            "selected": sorted(selected),
            "live": sorted(live),
            "live_status": live_status,
        }
        if live_status not in {"complete", "not_required"}:
            return set(), "incomplete", "networkgroup_dependency_incomplete", dependency_coverage

        expected: set[str] = set()
        visiting: set[str] = set()
        visited: set[str] = set()

        def resolve(name: str) -> tuple[str, str | None]:
            if name in visited:
                return "verified", None
            if name in visiting:
                return "incomplete", "networkgroup_dependency_cycle"
            record = selected.get(name, live.get(name))
            if not isinstance(record, dict):
                return "incomplete", "networkgroup_dependency_unavailable"
            if record.get("state", "present") != "present" or record.get("enabled") is not True:
                return "incomplete", "networkgroup_dependency_unavailable"
            kind = record.get("type")
            if kind in {"urltable", "urljson", "dynipv6host", "port"}:
                return "unsupported", "dynamic_networkgroup_member"
            if kind not in {"host", "network", "networkgroup"}:
                return "unsupported", "networkgroup_member_type_unavailable"
            values = record.get("content")
            if not isinstance(values, list) or not values:
                return "incomplete", "networkgroup_dependency_incomplete"
            if any(not isinstance(value, str) or not value for value in values):
                return "incomplete", "networkgroup_dependency_incomplete"
            visiting.add(name)
            for value in values:
                try:
                    expected.add(str(ipaddress.ip_network(value, strict=False)))
                    continue
                except ValueError:
                    pass
                if not ALIAS_NAME.fullmatch(value):
                    visiting.discard(name)
                    return "incomplete", "networkgroup_dependency_unavailable"
                status, reason = resolve(value)
                if status != "verified":
                    visiting.discard(name)
                    return status, reason
            visiting.discard(name)
            visited.add(name)
            return "verified", None

        status, reason = resolve(alias)
        if status != "verified":
            return set(), status, reason, dependency_coverage
        canonical, canonical_status = self._canonical_networks(list(expected))
        if canonical_status != "verified":
            return set(), "incomplete", "networkgroup_dependency_incomplete", dependency_coverage
        dependency_coverage["members"] = len(canonical)
        return canonical, "verified", None, dependency_coverage

    def _networkgroup_definitions(
        self, context: dict[str, Any] | None, *, require_live: bool = True
    ) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]], str]:
        """Read the narrow, internal context contract used by group checks."""
        selected: dict[str, dict[str, Any]] = {}
        live: dict[str, dict[str, Any]] = {}
        if isinstance(context, dict):
            allowed = {"selected", "live_aliases", "observations"}
            if set(context) - allowed or {"live_aliases", "observations"} <= set(context):
                return selected, live, "incomplete"
            if "selected" in context:
                value = context["selected"]
                if not isinstance(value, list):
                    return selected, live, "incomplete"
                for item in value:
                    if (not isinstance(item, dict) or item.get("resource") != "aliases"
                            or not isinstance(item.get("identity"), list)
                            or len(item["identity"]) != 1 or not isinstance(item["identity"][0], str)
                            or not isinstance(item.get("desired"), dict)):
                        return selected, live, "incomplete"
                    name = item["identity"][0]
                    if name in selected:
                        return selected, live, "incomplete"
                    record = deepcopy(item["desired"])
                    declared_name = record.get("name")
                    if declared_name is not None and declared_name != name:
                        return selected, live, "incomplete"
                    record["name"] = name
                    selected[name] = record
            if not require_live:
                return selected, live, "not_required"
            if "live_aliases" in context:
                value = context["live_aliases"]
                if not isinstance(value, list):
                    return selected, live, "incomplete"
                for record in value:
                    if not isinstance(record, dict) or not isinstance(record.get("name"), str) \
                            or not record["name"] or record["name"] in live:
                        return selected, live, "incomplete"
                    live[record["name"]] = deepcopy(record)
                return selected, live, "complete"
            if "observations" in context:
                observations = context["observations"]
                aliases = observations.get("aliases") if isinstance(observations, dict) else None
                if not isinstance(aliases, dict) or aliases.get("status") != "complete":
                    return selected, live, "incomplete"
                objects = aliases.get("objects")
                if not isinstance(objects, list):
                    return selected, live, "incomplete"
                for item in objects:
                    if (not isinstance(item, dict) or item.get("resource") not in {None, "aliases"}
                            or not isinstance(item.get("identity"), list)
                            or len(item["identity"]) != 1 or not isinstance(item["identity"][0], str)
                            or not isinstance(item.get("configuration"), dict)):
                        return selected, live, "incomplete"
                    name = item["identity"][0]
                    if name in live:
                        return selected, live, "incomplete"
                    record = deepcopy(item["configuration"])
                    declared_name = record.get("name")
                    if declared_name is not None and declared_name != name:
                        return selected, live, "incomplete"
                    record["name"] = name
                    live[name] = record
                return selected, live, "complete"
            if any(key in context for key in ("live", "observed", "aliases", "selected_aliases")):
                return selected, live, "incomplete"
        if not require_live:
            return selected, live, "not_required"
        try:
            rows = self.list("alias")
        except (UnsupportedRead, _HttpFailure, TypeError, ValueError):
            return selected, live, "unavailable"
        if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
            return selected, live, "malformed"
        for row in rows:
            flat = _flatten_provider_row(self._provider_row(row), "aliases")
            if "content" in flat:
                flat["content"] = _as_list(flat["content"])
            if "enabled" in flat:
                flat["enabled"] = _coerce_bool(flat["enabled"])
            name = flat.get("name")
            if not isinstance(name, str) or not name or name in live:
                return selected, live, "incomplete"
            live[name] = flat
        return selected, live, "complete"


class ReaderError(ValueError):
    """Invalid reader target, credentials, or resource selection."""


@dataclass(frozen=True)
class _Fetch:
    rows: list[dict[str, Any]]
    pages: int
    total: int | None
    complete: bool
    reason: str | None = None


_IDENTITY_DESCRIPTION = re.compile(
    r"^iaas:opnsense:(?P<resource>filter|dnat|one-to-one-nat):"
    r"(?P<scope>[a-z0-9][a-z0-9-]*):(?P<slug>[a-z0-9][a-z0-9-]*)$"
)

_STANDARD_FIELDS: dict[str, tuple[str, ...]] = {
    "aliases": ("name", "type", "content", "description", "enabled", "updatefreq_days"),
    "vips": ("description", "interface", "address", "bind", "expand"),
    "gateways": (
        "name", "interface", "ip_protocol", "gateway", "default_gw", "far_gw",
        "monitor_disable", "monitor_noroute", "monitor", "force_down", "latency_low",
        "latency_high", "loss_low", "loss_high", "interval", "time_period",
        "loss_interval", "data_length", "priority", "weight", "description",
    ),
    "filter-rules": (
        "scope", "slug", "enabled", "sequence", "interface", "direction", "action",
        "quick", "ip_protocol", "protocol", "source_net", "destination_net",
        "source_invert", "source_port", "destination_invert", "destination_port", "gateway", "log",
    ),
    "dnat": (
        "scope", "slug", "enabled", "sequence", "interface", "ip_protocol", "protocol",
        "source_net", "destination_net", "target", "nat_reflection", "associated_rule",
        "source_port", "destination_port", "local_port", "source_invert", "destination_invert",
        "log", "pool_opts", "tag", "tagged",
    ),
    "one-to-one-nat": (
        "scope", "slug", "enabled", "sequence", "interface", "type", "external", "source_net",
        "destination_net", "nat_reflection", "source_invert", "destination_invert", "log",
    ),
    "interface-groups": ("name", "members", "gui_group", "sequence", "description"),
}

_DEFAULTS: dict[str, dict[str, Any]] = {
    "filter-rules": {
        "source_invert": False, "destination_invert": False, "log": True,
    },
    "dnat": {
        "source_port": "", "destination_port": "", "local_port": "", "source_invert": False,
        "destination_invert": False, "log": False, "pool_opts": "", "tag": "", "tagged": "",
    },
    "one-to-one-nat": {"source_invert": False, "destination_invert": False, "log": False},
    "interface-groups": {"description": ""},
}

_LIST_FIELDS = {
    "aliases": {"content"},
    "vips": set(),
    "gateways": set(),
    "filter-rules": {"interface"},
    "dnat": {"interface"},
    "one-to-one-nat": set(),
    "interface-groups": {"members"},
}

_BOOL_FIELDS = {
    "enabled", "bind", "expand", "default_gw", "far_gw", "monitor_disable", "monitor_noroute",
    "force_down", "quick", "source_invert", "destination_invert", "log", "gui_group",
}

# Names emitted by the Collection's simplify_translate layer and the common
# nested names of its native API responses.  Canonical Collection output uses
# the left hand side already; accepting the right hand side makes the adapter
# useful with representative raw response fixtures without exposing those
# raw fields in its result.
_FIELD_ALIASES = {
    "descr": "description", "ifname": "interface", "ipprotocol": "ip_protocol",
    "defaultgw": "default_gw", "fargw": "far_gw", "latencylow": "latency_low",
    "latencyhigh": "latency_high", "losslow": "loss_low", "losshigh": "loss_high",
    "disabled": "enabled", "nobind": "bind", "noexpand": "expand", "nogroup": "gui_group",
    "natreflection": "nat_reflection", "pass": "associated_rule", "nordr": "no_port_forward",
    "source_not": "source_invert", "destination_not": "destination_invert",
    "updatefreq": "updatefreq_days", "source-port": "source_port", "destination-port": "destination_port",
    "local-port": "local_port", "target-port": "target_port", "poolopts": "pool_opts", "no-nat": "no_nat",
    "interfacenot": "interface_invert", "disablereplyto": "disable_replyto", "allowopts": "allow_opts",
    "statetype": "state_type", "state-policy": "state_policy", "statetimeout": "state_timeout",
    "max": "max_states", "max-src-nodes": "max_src_nodes", "max-src-states": "max_src_states",
    "max-src-conn": "max_src_conn", "max-src-conn-rate": "max_src_conn_rate", "max-src-conn-rates": "max_src_conn_rates",
    "adaptivestart": "adaptive_start", "adaptiveend": "adaptive_end", "set-prio": "set_prio",
    "set-prio-low": "set_prio_low", "tcpflags1": "tcp_flags", "tcpflags2": "tcp_flags_clear",
    "sched": "schedule", "icmptype": "icmp_type", "icmp6type": "icmpv6_type", "divert-to": "divert_to",
    "advbase": "advertising_base", "advskew": "advertising_skew",
}

_SELECT_FIELDS = {
    "type", "interface", "mode", "vhid", "advertising_base", "advertising_skew", "action", "direction",
    "ip_protocol", "protocol", "gateway", "replyto", "state_type", "state_policy", "overload", "prio",
    "set_prio", "set_prio_low", "schedule", "tos", "members", "nat_reflection", "pool_opts", "associated_rule",
    "icmp_type", "icmpv6_type", "tcp_flags", "tcp_flags_clear", "received-on",
    "divert_to", "shaper1", "shaper2", "authtype", "proto",
}

_INVERTED_FIELDS = {"disabled": "enabled", "nobind": "bind", "noexpand": "expand", "nogroup": "gui_group"}

# Provider fields which carry configuration semantics but are deliberately
# outside this workflow's standard schema. UUIDs and transport metadata are
# intentionally absent so irrelevant native fields do not reject a row.
_NATIVE_UNEXPRESSED: dict[str, set[str]] = {
    "aliases": {"interface", "path_expression", "authtype", "proto", "counters"},
    "vips": {"mode", "gateway", "password", "vhid", "advertising_base", "advertising_skew", "peer", "peer6", "nosync"},
    "gateways": {"nosync", "monitor_killstates", "monitor_killstates_priority"},
    "filter-rules": {"interface_invert", "tag", "tagged", "replyto", "disable_replyto", "allow_opts",
                      "state_type", "state_policy", "state_timeout", "max_states", "max_src_nodes",
                      "max_src_states", "max_src_conn", "max_src_conn_rate", "max_src_conn_rates",
                      "overload", "adaptive_start", "adaptive_end", "prio", "set_prio", "set_prio_low",
                      "tcp_flags", "tcp_flags_clear", "schedule", "tos", "icmp_type", "icmpv6_type", "divert_to",
                      "shaper1", "shaper2", "received-on", "received-on-not", "tcpflags_any",
                      "nosync", "nopfsync"},
    "dnat": {"target_port", "no_nat", "nosync"},
    "one-to-one-nat": {"nosync"},
    "interface-groups": set(),
}

# Volatile model fields, scoped to the resource that defines them.
_NATIVE_METADATA = {
    "aliases": {"current_items", "eval_match", "eval_nomatch", "in_block_b", "in_block_p",
                "in_pass_b", "in_pass_p", "out_block_b", "out_block_p", "out_pass_b", "out_pass_p"},
    "filter-rules": {"sort_order", "prio_group", "%source_net", "%destination_net"},
}
_NATIVE_FALSE_FIELDS = {"nosync", "nopfsync", "monitor_killstates", "monitor_killstates_priority",
                        "received-on-not", "tcpflags_any", "counters"}

_IGNORED_NATIVE_FIELDS = {
    "uuid", "id", "created", "updated", "modified", "timestamp", "selected", "key", "value",
    "network", "subnet", "subnet_bits", "source", "destination", "source_not", "destination_not",
    "packets", "bytes", "evaluations", "states", "last_updated",
    "disabled", "nobind", "noexpand", "nogroup", "ifname", "descr", "ipprotocol", "defaultgw", "fargw",
    "latencylow", "latencyhigh", "losslow", "losshigh", "natreflection", "pass", "nordr",
}

_INTEGER_FIELDS = {
    "sequence", "latency_low", "latency_high", "loss_low", "loss_high", "interval", "time_period",
    "loss_interval", "data_length", "priority", "weight", "state_timeout",
}


def _validate_target(target: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(target, dict):
        raise ReaderError("target must be a mapping")
    host = target.get("host")
    endpoint = target.get("endpoint")
    ssl_verify = target.get("ssl_verify")
    if not isinstance(host, str) or not host or any(ch in host for ch in "\r\n\0"):
        raise ReaderError("target.host must be a non-empty inventory identifier")
    if not isinstance(endpoint, str) or not endpoint:
        raise ReaderError("target.endpoint must be an explicit URL")
    if type(ssl_verify) is not bool:
        raise ReaderError("target.ssl_verify must be a boolean")
    try:
        parsed = urlsplit(endpoint)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError
        if parsed.username is not None or parsed.password is not None or parsed.query or parsed.fragment:
            raise ValueError
        if parsed.path not in {"", "/"}:
            raise ValueError
        _ = parsed.port
    except (TypeError, ValueError):
        raise ReaderError("target.endpoint must be a host-only HTTP(S) URL") from None
    return {"host": host, "endpoint": endpoint.rstrip("/"), "ssl_verify": ssl_verify}


def _validate_credentials(credentials: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(credentials, dict):
        raise ReaderError("credentials must be a mapping")
    result = dict(credentials)
    for key in ("OPNSENSE_API_KEY", "OPNSENSE_API_SECRET"):
        if key in result and (not isinstance(result[key], str) or not result[key]):
            raise ReaderError(f"{key} must be a non-empty injected value")
    return result


def _copy_value(value: Any) -> Any:
    return deepcopy(value)


def _sort_list(value: Any) -> Any:
    if not isinstance(value, list):
        return value
    return sorted((_copy_value(item) for item in value), key=lambda item: repr(item))


def _coerce_bool(value: Any) -> Any:
    if type(value) is bool:
        return value
    if isinstance(value, int) and value in (0, 1):
        return bool(value)
    if isinstance(value, str):
        if value.lower() in {"1", "true", "yes", "on"}:
            return True
        if value.lower() in {"0", "false", "no", "off"}:
            return False
    return value


def _coerce_scalar(value: Any) -> Any:
    """Match simplify_translate's numeric conversion without changing names."""
    if isinstance(value, str) and value.isnumeric():
        return int(value)
    return value


def _selected(value: Any, *, multiple: bool = False) -> Any:
    """Decode OPNsense select/select-list wire values used by model responses."""
    selected: list[Any] = []
    if isinstance(value, dict):
        for key, option in value.items():
            if not isinstance(option, dict) or type(_coerce_bool(option.get("selected"))) is not bool:
                raise _HttpFailure("incomplete", "malformed_native_selector")
            if _coerce_bool(option["selected"]):
                # Model response keys are identifiers; `value` is a display label.
                selected.append(key)
    elif isinstance(value, list) and any(isinstance(item, dict) for item in value):
        for option in value:
            if not isinstance(option, dict) or type(_coerce_bool(option.get("selected"))) is not bool:
                raise _HttpFailure("incomplete", "malformed_native_selector")
            if _coerce_bool(option["selected"]):
                selected.append(option.get("key", option.get("value")))
    else:
        return value
    if (any(not isinstance(item, (str, int)) or isinstance(item, bool) for item in selected)
            or len(set(selected)) != len(selected) or (not multiple and len(selected) > 1)):
        raise _HttpFailure("incomplete", "malformed_native_selector")
    if multiple:
        return [_coerce_scalar(item) for item in selected]
    return _coerce_scalar(selected[0]) if selected else ""


def _as_list(value: Any) -> Any:
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        # The Collection's Alias helper turns a provider content mapping into
        # its non-empty keys before returning ``get_existing``.
        return [key for key in value if key != ""]
    if isinstance(value, str):
        if not value:
            return []
        return [item for item in re.split(r"[,\n]", value) if item != ""]
    return value


def _flatten_provider_row(row: dict[str, Any], resource: str | None = None) -> dict[str, Any]:
    result = deepcopy(row)
    for source, destination in _INVERTED_FIELDS.items():
        if destination not in result and source in row:
            value = _coerce_bool(row[source])
            result[destination] = not value if type(value) is bool else value
    for source, destination in _FIELD_ALIASES.items():
        if destination not in result and source in result:
            result[destination] = deepcopy(result[source])
    if resource == "interface-groups" and "name" not in result and isinstance(row.get("ifname"), str):
        result["name"] = row["ifname"]
    for section, prefix in (("source", "source"), ("destination", "destination")):
        nested = row.get(section)
        if isinstance(nested, dict):
            for key, value in nested.items():
                if key in {"network", "port"}:
                    result[f"{prefix}_{'net' if key == 'network' else key}"] = deepcopy(value)
                elif key == "not":
                    result[f"{prefix}_invert"] = deepcopy(value)
    if resource == "interface-groups" and row.get("nogroup") == "" and result.get("gui_group") in (None, ""):
        result["gui_group"] = True
    for field in _SELECT_FIELDS:
        if field in result:
            multiple = (field in {"members", "icmp_type", "icmpv6_type", "tcp_flags", "tcp_flags_clear",
                                  "received-on", "proto"}
                        or (field == "interface" and resource in {"filter-rules", "dnat"}))
            result[field] = _selected(result[field], multiple=multiple)
    for field in _BOOL_FIELDS:
        if field in result:
            result[field] = _coerce_bool(result[field])
    for field in _INTEGER_FIELDS:
        if field in result:
            result[field] = _coerce_scalar(result[field])
    if "updatefreq_days" in result and isinstance(result["updatefreq_days"], (int, float)) \
            and not isinstance(result["updatefreq_days"], bool):
        value = float(result["updatefreq_days"])
        result["updatefreq_days"] = str(int(value) if value.is_integer() else round(value, 1))
    # Raw API VIPs use network/subnet_bits while the Collection's list result
    # exposes address.  Only combine literal values; malformed values remain
    # unknown and never become a fabricated configuration.
    if "address" not in result:
        network = result.get("subnet", result.get("network"))
        prefix = _coerce_scalar(result.get("subnet_bits"))
        if isinstance(network, str) and isinstance(prefix, int) and 0 <= prefix <= 128:
            result["address"] = f"{network}/{prefix}"
    return result


def _parse_identity(resource: str, row: dict[str, Any]) -> list[str] | None:
    if resource in {"aliases", "interface-groups"}:
        value = row.get("name")
        return [value] if isinstance(value, str) and value else None
    if resource == "vips":
        address, interface = row.get("address"), row.get("interface")
        if isinstance(address, str) and address and isinstance(interface, str) and interface:
            return [address, interface]
        return None
    if resource == "gateways":
        name, gateway = row.get("name"), row.get("gateway")
        if isinstance(name, str) and name and isinstance(gateway, str) and gateway:
            return [name, gateway]
        native_id = row.get("uuid", row.get("id"))
        if isinstance(name, str) and name and gateway == "" and isinstance(native_id, str) and native_id:
            return ["native:" + native_id]
        return None
    description = row.get("description", row.get("descr"))
    native_id = row.get("uuid", row.get("id"))
    if not isinstance(description, str) or not description:
        return ["native:" + native_id] if isinstance(native_id, str) and native_id else None
    match = _IDENTITY_DESCRIPTION.fullmatch(description)
    if not match:
        native_id = row.get("uuid", row.get("id"))
        return ["native:" + native_id] if isinstance(native_id, str) and native_id else None
    expected = {"filter-rules": "filter", "dnat": "dnat", "one-to-one-nat": "one-to-one-nat"}[resource]
    if match.group("resource") != expected:
        return None
    return [f"iaas:opnsense:{expected}:{match.group('scope')}:{match.group('slug')}"]


def _references(resource: str, row: dict[str, Any], configuration: dict[str, Any] | None) -> list[str]:
    source = configuration or _flatten_provider_row(row, resource)
    refs: set[str] = set()
    aliases: set[str] = set()
    fields = ["source_net", "destination_net", "target", "external", "source_port", "destination_port", "local_port"]
    if resource == "aliases" and source.get("type") == "networkgroup":
        fields.append("content")
    for field in fields:
        value = _as_list(source.get(field))
        values = value if isinstance(value, list) else [value]
        values = [token.strip() for item in values if isinstance(item, str)
                  for token in re.split(r"[,\n]", item)]
        for item in values:
            if not isinstance(item, str) or item in {"", "any", "(self)"} or item.isdecimal():
                continue
            if "-" in item and all(part.isdecimal() for part in item.split("-")):
                continue
            try:
                ipaddress.ip_network(item, strict=False)
                continue
            except ValueError:
                pass
            if re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.-]*", item):
                aliases.add(item)
    if aliases:
        refs.update("aliases:" + name for name in aliases)
    interface = source.get("interface")
    interfaces = interface if isinstance(interface, list) else [interface]
    groups = [item for item in interfaces if isinstance(item, str) and re.fullmatch(r"^(?![0-9])[A-Za-z0-9_]{1,15}(?<![0-9])$", item)]
    if groups and resource in {"filter-rules", "dnat", "one-to-one-nat"}:
        refs.update("interface-groups:" + name for name in set(groups))
    gateway = source.get("gateway")
    if resource == "filter-rules" and isinstance(gateway, str) and gateway:
        refs.add("gateways:" + gateway)
    # Keep only stable reverse-reference labels.  Do not retain raw provider
    # rows, counters, credentials, or arbitrary API response fields.
    return sorted(refs)


def _configuration(resource: str, row: dict[str, Any]) -> tuple[dict[str, Any] | None, str | None]:
    flat = _flatten_provider_row(row, resource)
    if resource == 'vips' and (flat.get('mode') not in {None, 'ipalias'}
                               or ('subnet' in row and 'mode' not in flat)):
        return None, 'unsupported_vip_mode'
    if resource == 'dnat' and (_coerce_bool(flat.get('no_port_forward', False)) is not False
                               or ('source' in row and 'no_port_forward' not in flat)):
        return None, 'unsupported_no_port_forward_mode'
    if resource == 'gateways' and flat.get('enabled', True) is not True:
        return None, 'disabled_gateway_not_expressible'
    unexpressed = _unexpressed_fields(resource, row, flat)
    if unexpressed:
        return None, "unexpressed_native_fields:" + ",".join(unexpressed)
    if resource in {"filter-rules", "dnat", "one-to-one-nat"}:
        identity = _parse_identity(resource, flat)
        if not identity or len(identity) != 1:
            return None, "unrecognized_managed_identity"
        match = _IDENTITY_DESCRIPTION.fullmatch(str(flat.get("description", "")))
        if match is None:
            return None, "unrecognized_managed_identity"
        flat["scope"] = match.group("scope")
        flat["slug"] = match.group("slug")
    fields = _STANDARD_FIELDS[resource]
    record: dict[str, Any] = {field: _copy_value(flat[field]) for field in fields if field in flat}
    for field in _LIST_FIELDS[resource]:
        if field in record:
            record[field] = _as_list(record[field])
    for field in _BOOL_FIELDS:
        if field in record:
            record[field] = _coerce_bool(record[field])
    for field, default in _DEFAULTS.get(resource, {}).items():
        record.setdefault(field, _copy_value(default))
    if resource == "aliases" and record.get("type") != "urltable" and record.get("updatefreq_days") == "":
        # The model emits this empty optional field for every alias type.
        # Preserve non-empty values so unsupported configuration still fails.
        record.pop("updatefreq_days")
    if resource == "filter-rules":
        # The standard validator treats an explicitly supplied empty port as
        # invalid; the Collection's module default is applied later by the
        # writer.  Omit empty provider readback values so they compare with
        # declarations that leave the optional field absent.
        for field in ("source_port", "destination_port"):
            if record.get(field) == "":
                record.pop(field, None)
        if record.get('gateway') == '':
            record.pop('gateway')
        # The model returns multi-value fields as CSV, while the standard
        # validator accepts lists. Decode before validation, not only afterward.
        for field in ("source_net", "destination_net", "source_port", "destination_port"):
            if field in record:
                record[field] = _as_list(record[field])
    record["state"] = "present"
    try:
        _validate_readback(resource, record)
        normalized = normalize_desired(resource, record)
    except Exception as error:  # provider-shaped but non-standard data is unknown
        return None, f"unrepresentable_configuration:{type(error).__name__}"
    return normalized, None


def _validate_readback(resource: str, record: dict[str, Any]) -> None:
    """Check provider completeness without applying cross-resource safety context.

    The full declaration validator runs later on the caller's selected
    documents.  A live filter rule has no declaration context here, so its
    interface/address safety proof must not be re-evaluated as if aliases and
    interface networks were absent.
    """
    if resource != "filter-rules":
        validate_document(resource, {TOP_LEVEL[resource]: [record]})
        return
    if record.get('action') not in {'pass', 'block', 'reject'}:
        raise ValidationError('unsupported native filter action')
    # Validate every standard field without treating observation of an existing
    # deny rule as a request to authorize it. Actual desired documents still
    # pass the full safety validator with their explicit context.
    probe = {**record, 'action': 'pass'}
    validate_document(resource, {TOP_LEVEL[resource]: [probe]})


def _unexpressed_fields(resource: str, row: dict[str, Any], flat: dict[str, Any]) -> list[str]:
    fields = _NATIVE_UNEXPRESSED.get(resource, set())
    found = []
    defaults = {'vips': {'mode': 'ipalias', 'advertising_base': 1, 'advertising_skew': 0},
                'gateways': {'enabled': True}, 'filter-rules': {'state_type': 'keep'}}.get(resource, {})
    for field in fields:
        value = flat.get(field, row.get(field))
        if field in _NATIVE_FALSE_FIELDS:
            if value is None or value == "" or _coerce_bool(value) is False:
                continue
            found.append(field)
            continue
        if field in {'interface_invert', 'disable_replyto', 'allow_opts'}:
            value = _coerce_bool(value)
        if field in defaults and str(value) == str(defaults[field]):
            continue
        if value not in (None, "", [], {}, False):
            found.append(field)
    for field, value in row.items():
        canonical = _FIELD_ALIASES.get(field, field)
        if canonical in defaults and str(flat.get(canonical, value)) == str(defaults[canonical]):
            continue
        if canonical in fields:
            continue
        if field in _NATIVE_METADATA.get(resource, set()):
            continue
        if field in _IGNORED_NATIVE_FIELDS or canonical in _STANDARD_FIELDS[resource]:
            continue
        if field in {"description", "state", "source", "destination"}:
            continue
        # Unknown fields have no established false/zero default. Only known
        # native fields above may use their existing neutral-value handling.
        if value not in (None, "", [], {}):
            found.append(field)
    return sorted(set(found))


def normalize_desired(resource: str, record: dict[str, Any]) -> dict[str, Any]:
    """Return a validator-backed, comparison-stable standard declaration.

    This function deliberately does not infer resource identity or ownership.
    It only supplies provider-compatible optional defaults and stable ordering
    for fields whose Collection representation is a set-like list. ``state``
    remains explicit. Full cross-resource validation belongs to the caller's
    selected declaration document, where filter safety context is available.
    """

    if resource not in SUPPORTED_RESOURCES:
        raise ReaderError(f"unsupported OPNsense resource: {resource}")
    if not isinstance(record, dict):
        raise ReaderError("resource declaration must be a mapping")
    result = deepcopy(record)
    if result.get("state") == "present":
        for field, default in _DEFAULTS.get(resource, {}).items():
            result.setdefault(field, deepcopy(default))
        for field in _LIST_FIELDS[resource]:
            if field in result:
                result[field] = _sort_list(result[field])
        if resource == "filter-rules":
            for field in ("source_net", "destination_net", "source_port", "destination_port"):
                if field in result:
                    value = _as_list(result[field])
                    if not isinstance(value, list):
                        value = [value]
                    result[field] = _sort_list([str(item) for item in value])
            protocol = result.get('protocol')
            if isinstance(protocol, str):
                result['protocol'] = {'icmpv6': 'ICMPv6', 'any': 'any'}.get(protocol.lower(), protocol.upper())
        elif resource == "dnat":
            for field in ("source_net", "destination_net"):
                if isinstance(result.get(field), list):
                    result[field] = ",".join(sorted(str(item) for item in result[field]))
            for field in ("source_port", "destination_port", "local_port"):
                if field in result and isinstance(result[field], int):
                    result[field] = str(result[field])
            if isinstance(result.get("protocol"), str):
                result["protocol"] = result["protocol"].lower()
        if resource == 'aliases' and result.get('type') == 'urltable' and 'updatefreq_days' in result:
            result['updatefreq_days'] = format(Decimal(str(result['updatefreq_days'])).normalize(), 'f')
    return result


def _invoke_list(transport: Any, target: str, page: int) -> Any:
    method = getattr(transport, "list", None)
    if callable(method):
        try:
            return method(target, page=page, page_size=MAX_PAGE_ROWS)
        except TypeError as first:
            try:
                return method(target)
            except TypeError:
                raise first
    method = getattr(transport, "read", None)
    if callable(method):
        return method(target, page=page, page_size=MAX_PAGE_ROWS)
    method = getattr(transport, "call", None)
    if callable(method):
        return method("list", target=target, page=page, page_size=MAX_PAGE_ROWS)
    raise UnsupportedRead("transport_has_no_read_only_list_method")


def _fetch(transport: Any, target: str) -> _Fetch:
    rows: list[dict[str, Any]] = []
    total: int | None = None
    for page in range(1, MAX_PAGES + 1):
        response = _invoke_list(transport, target, page)
        if isinstance(response, list):
            if page != 1 or len(response) > MAX_PAGE_ROWS or any(not isinstance(row, dict) for row in response):
                return _Fetch([], page, None, False, "malformed_or_unbounded_collection_result")
            return _Fetch(deepcopy(response), 1, len(response), True)
        if not isinstance(response, dict):
            return _Fetch([], page, None, False, "malformed_collection_page")
        page_rows = response.get("rows")
        if not isinstance(page_rows, list) or any(not isinstance(row, dict) for row in page_rows):
            # Collection list output may wrap its already complete result in
            # ``data``; accept only a list there, never arbitrary response data.
            data = response.get("data")
            if page == 1 and isinstance(data, list) and len(data) <= MAX_PAGE_ROWS and all(isinstance(row, dict) for row in data):
                return _Fetch(deepcopy(data), 1, len(data), True)
            return _Fetch([], page, None, False, "malformed_collection_page")
        current = response.get("current")
        page_total = response.get("total")
        row_count = response.get("rowCount", len(page_rows))
        if current != page or not isinstance(page_total, int) or page_total < 0 or not isinstance(row_count, int) or row_count < 0:
            return _Fetch([], page, None, False, "malformed_collection_page")
        if len(page_rows) > MAX_PAGE_ROWS or page_total < len(page_rows):
            return _Fetch([], page, page_total, False, "malformed_collection_page")
        if total is None:
            total = page_total
        elif total != page_total:
            return _Fetch([], page, total, False, "inconsistent_collection_total")
        rows.extend(deepcopy(page_rows))
        if len(rows) > total:
            return _Fetch([], page, total, False, "inconsistent_collection_total")
        if len(rows) == total:
            return _Fetch(rows, page, total, True)
        if not page_rows:
            return _Fetch(rows, page, total, False, "incomplete_collection_page")
    return _Fetch(rows, MAX_PAGES, total, False, "configuration_bound_exceeded")


def _interface_choices(transport: Any) -> tuple[list[str], str]:
    """Read provider-model interface choices when the injected client exposes them.

    The pinned resource modules validate interface names against appliance
    choices, but the generic ``list`` target itself does not include that
    model metadata.  A fixed client may expose either ``interfaces`` or
    ``interface_choices``; absence is reported as unavailable so planning can
    keep physical-interface admission conservative.
    """

    for name in ("interfaces", "interface_choices"):
        method = getattr(transport, name, None)
        if not callable(method):
            continue
        try:
            value = method()
        except UnsupportedRead:
            return [], "unavailable"
        except Exception:
            return [], "failed"
        if isinstance(value, dict):
            value = value.get("interfaces", value.get("choices", value.get("data", value)))
        if not isinstance(value, list):
            return [], "malformed"
        result: list[str] = []
        for item in value:
            if isinstance(item, str) and item:
                result.append(item)
            elif isinstance(item, dict):
                candidate = item.get("name", item.get("key", item.get("value", item.get("ifname"))))
                if isinstance(candidate, str) and candidate:
                    result.append(candidate)
                else:
                    return [], "malformed"
            else:
                return [], "malformed"
        return sorted(set(result)), "complete"
    return [], "unavailable"


class Reader:
    """Read selected OPNsense resources through a fixed client only."""

    def __init__(
        self,
        target: dict[str, Any],
        credentials: dict[str, Any],
        transport: ReadTransport | Any | None = None,
    ):
        self.target = _validate_target(target)
        self.credentials = _validate_credentials(credentials)
        self.transport = transport if transport is not None else FixedCollectionTransport(self.target, self.credentials)

    def read(self, resources: list[str] | tuple[str, ...]) -> dict[str, dict[str, Any]]:
        """Read exactly the requested classes and return redacted observations."""

        if not isinstance(resources, (list, tuple)) or isinstance(resources, str):
            raise ReaderError("resources must be an explicit list")
        if len(set(resources)) != len(resources):
            raise ReaderError("resource selection contains duplicates")
        for resource in resources:
            if resource not in SUPPORTED_RESOURCES:
                raise ReaderError(f"unsupported OPNsense resource: {resource}")
        return {resource: self._read_one(resource) for resource in resources}

    def _read_one(self, resource: str) -> dict[str, Any]:
        target = COLLECTION_TARGETS[resource]
        base = {
            "resource": resource,
            "collection_target": target,
            "status": "failed",
            "objects": [],
            "coverage": {"scope": "selected_resource", "pages": 0, "rows": 0, "total": None, "complete": False},
            "reason": None,
            "read_only": True,
        }
        interfaces, interface_status = _interface_choices(self.transport)
        base["interfaces"] = interfaces
        base["coverage"]["interfaces"] = interface_status
        try:
            fetched = _fetch(self.transport, target)
        except _HttpFailure as error:
            base.update(status=error.status, reason=error.reason)
            return base
        except UnsupportedRead as error:
            base.update(status="unsupported", reason=str(error))
            return base
        except Exception as error:
            base.update(status="failed", reason=type(error).__name__)
            return base
        base["coverage"].update(pages=fetched.pages, rows=len(fetched.rows), total=fetched.total, complete=fetched.complete)
        if not fetched.complete:
            base.update(status="incomplete", reason=fetched.reason or "incomplete_collection_result")
            return base
        objects: list[dict[str, Any]] = []
        incomplete_reasons: list[str] = []
        identities: set[tuple[str, ...]] = set()
        for row in fetched.rows:
            try:
                identity = _parse_identity(resource, _flatten_provider_row(row, resource))
                configuration, reason = _configuration(resource, row)
                references = _references(resource, row, configuration)
            except _HttpFailure as error:
                incomplete_reasons.append(error.reason)
                continue
            if identity is None:
                incomplete_reasons.append("missing_identity")
                continue
            key = tuple(identity)
            if key in identities:
                incomplete_reasons.append("duplicate_identity")
                continue
            identities.add(key)
            objects.append({
                "identity": identity,
                "configuration": configuration,
                "references": references,
                "recovery": "expressible" if configuration is not None else "manual_required",
                "reason": reason,
            })
            if resource == "gateways" and isinstance(row.get("name"), str) and row["name"]:
                objects[-1]["label"] = "gateways:" + row["name"]
        base["objects"] = objects
        # A complete listing can contain identified native objects whose
        # configuration is outside the standard schema.  Keep those objects
        # as unknown/manual recovery while reserving incomplete for broken
        # enumeration or identity ambiguity.
        if incomplete_reasons:
            base.update(status="incomplete", reason=sorted(set(incomplete_reasons)))
        else:
            base["status"] = "complete"
        return base

    def close(self) -> None:
        close = getattr(self.transport, "close", None)
        if callable(close):
            close()

    def active_check(
        self,
        resource: str,
        identity: list[str],
        desired: dict[str, Any],
        *,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        method = getattr(self.transport, "active_check", None)
        if not callable(method):
            return {"status": "unsupported", "reason": "active_observation_unavailable",
                    "coverage": "saved_configuration_only"}
        try:
            if context is None:
                result = method(resource, identity, desired)
            else:
                result = method(resource, identity, desired, context=context)
        except _HttpFailure as error:
            return {"status": "unsupported" if error.status == "unsupported" else "unknown", "reason": error.reason,
                    "coverage": "active_observation_unavailable"}
        except UnsupportedRead as error:
            return {"status": "unsupported", "reason": str(error),
                    "coverage": "saved_configuration_only"}
        except Exception as error:
            return {"status": "unknown", "reason": type(error).__name__,
                    "coverage": "active_observation_unavailable"}
        return result if isinstance(result, dict) else {
            "status": "unknown", "reason": "malformed_active_observation",
            "coverage": "active_observation_unavailable",
        }


__all__ = [
    "COLLECTION_TARGETS", "FixedCollectionTransport", "MAX_PAGE_ROWS", "MAX_PAGES", "Reader",
    "ReaderError", "ReadTransport", "SUPPORTED_RESOURCES", "UnsupportedRead", "normalize_desired",
]
