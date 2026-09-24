from copy import deepcopy

from iaas.opnsense_workflow.gateway_checks import check_gateway_current
from iaas.opnsense_workflow.reader import FixedCollectionTransport, Reader


TARGET = {"host": "firewall", "endpoint": "https://firewall.example", "ssl_verify": True}
CREDENTIALS = {"OPNSENSE_API_KEY": "key", "OPNSENSE_API_SECRET": "secret"}


DESIRED = {
    "name": "WAN",
    "interface": "wan",
    "gateway": "192.0.2.1",
    "monitor": "192.0.2.1",
    "monitor_disable": False,
}

ROUTES = [
    {"destination": "203.0.113.0/24", "gateway": "192.0.2.1", "netif": "igc0",
     "intf_description": "WAN", "id": "203.0.113.0/24,192.0.2.1"},
]

GATEWAY_ROWS = {"rows": [{
    "name": "WAN", "interface": "wan", "if": "igc0", "gateway": "192.0.2.1",
    "monitor": "192.0.2.1", "monitor_disable": False, "monitor_noroute": False,
    "status": "Online",
    "loss": "0", "delay": "1", "stddev": "0",
}], "current": 1, "rowCount": 1000, "total": 1}


def test_current_gateway_checks_do_not_require_default_route_or_ping_success():
    result = check_gateway_current(DESIRED, ROUTES, GATEWAY_ROWS)

    assert result["status"] == "unsupported"
    assert result["current_status"] == "verified"
    assert result["checks"]["interface"]["status"] == "verified"
    assert result["checks"]["physical_interface"]["status"] == "verified"
    assert result["checks"]["next_hop"]["status"] == "verified"
    assert result["checks"]["monitor_configuration"]["status"] == "verified"
    assert result["checks"]["route"]["status"] == "not_applicable"
    assert result["checks"]["runtime_status"]["status"] == "not_applicable"
    assert result["checks"]["runtime_status"]["reason"] == "runtime_status_informational_only"
    assert result["completion"] == {
        "status": "unknown", "reason": "gateway_reconfigure_not_correlated"
    }
    assert result["consumer"]["status"] == "unsupported"


def test_logical_interface_is_not_guessed_as_route_netif():
    status = deepcopy(GATEWAY_ROWS)
    status["rows"][0].pop("if")
    result = check_gateway_current(DESIRED, ROUTES, status)

    assert result["status"] == "unsupported"
    assert result["current_status"] == "verified"
    assert result["checks"]["interface"]["status"] == "verified"
    assert result["checks"]["physical_interface"]["status"] == "unknown"


def test_route_next_hop_mismatch_is_distinct_from_missing_fact():
    status = deepcopy(GATEWAY_ROWS)
    status["rows"][0]["gateway"] = "198.51.100.1"
    result = check_gateway_current(DESIRED, ROUTES, status)

    assert result["status"] == "failed"
    assert result["checks"]["next_hop"]["status"] == "failed"
    assert result["checks"]["next_hop"]["reason"] == "gateway_next_hop_mismatch"


def test_disabled_monitor_is_not_reported_as_runtime_success():
    desired = deepcopy(DESIRED)
    desired["monitor_disable"] = True
    status = deepcopy(GATEWAY_ROWS)
    status["rows"][0]["monitor_disable"] = True
    result = check_gateway_current(desired, ROUTES, status)

    assert result["status"] == "unsupported"
    assert result["current_status"] == "verified"
    assert result["checks"]["monitor_configuration"]["status"] == "not_applicable"
    assert result["checks"]["monitor_configuration"]["reason"] == "monitor_disabled_by_desired"


def test_missing_route_or_status_rows_is_unknown_and_never_completion():
    route_result = check_gateway_current(DESIRED, [], GATEWAY_ROWS)
    status_result = check_gateway_current(
        DESIRED, ROUTES, {"current": 1, "rowCount": 1000, "total": 0, "rows": []}
    )

    assert route_result["status"] == "unsupported"
    assert route_result["current_status"] == "verified"
    assert route_result["checks"]["route"]["status"] == "not_applicable"
    assert status_result["status"] == "unknown"
    assert status_result["reason"] == "gateway_status_missing_or_ambiguous"
    assert route_result["completion"]["status"] == "unknown"
    assert status_result["completion"]["status"] == "unknown"


def test_consumer_observation_is_passed_through_without_inference():
    consumer = {"status": "verified", "matches": True, "source": "pf_rules"}
    result = check_gateway_current(DESIRED, ROUTES, GATEWAY_ROWS, consumer)

    assert result["status"] == "verified"
    assert result["consumer"] == consumer
    assert result["completion"]["status"] == "unknown"


def test_failed_or_unknown_consumer_prevents_verified_overall_status():
    failed = check_gateway_current(
        DESIRED, ROUTES, GATEWAY_ROWS, {"status": "failed", "reason": "route_to_mismatch"}
    )
    unknown = check_gateway_current(
        DESIRED, ROUTES, GATEWAY_ROWS, {"status": "unknown", "reason": "consumer_unavailable"}
    )

    assert failed["current_status"] == "verified" and failed["status"] == "failed"
    assert unknown["current_status"] == "verified" and unknown["status"] == "unknown"


def test_empty_monitor_uses_native_gateway_default_without_forcing_a_target():
    desired = deepcopy(DESIRED)
    desired.pop("monitor")
    status = deepcopy(GATEWAY_ROWS)
    status["rows"][0]["monitor"] = ""
    result = check_gateway_current(desired, ROUTES, status, {"status": "not_applicable"})

    assert result["status"] == "verified"
    assert result["checks"]["monitor_configuration"]["status"] == "verified"
    assert result["checks"]["monitor_configuration"]["observed"]["mode"] == "gateway_default"


def test_explicit_monitor_host_route_is_the_only_route_requirement():
    expectation = {"purpose": "monitor_host", "destination": "192.0.2.1/32"}
    status = deepcopy(GATEWAY_ROWS)
    status["rows"][0]["monitor_noroute"] = False
    result = check_gateway_current(DESIRED, ROUTES, status, {"status": "not_applicable"},
                                  route_expectation=expectation)
    assert result["status"] == "failed"
    assert result["current_status"] == "failed"
    assert result["checks"]["route"]["status"] == "failed"


def test_pbr_route_expectation_is_unsupported_until_pf_consumer_observation():
    result = check_gateway_current(
        DESIRED, ROUTES, GATEWAY_ROWS, {"status": "not_applicable"},
        route_expectation={"purpose": "pbr_consumer", "destination": "203.0.113.0/24"},
    )
    assert result["status"] == "unsupported"
    assert result["current_status"] == "unsupported"
    assert result["checks"]["route"]["status"] == "unsupported"


def test_explicit_monitor_host_route_is_not_required_when_noroute_is_enabled():
    expectation = {"purpose": "monitor_host", "destination": "192.0.2.1/32"}
    status = deepcopy(GATEWAY_ROWS)
    status["rows"][0]["monitor_noroute"] = True
    result = check_gateway_current(DESIRED, None, status, {"status": "not_applicable"},
                                  route_expectation=expectation)

    assert result["status"] == "verified"
    assert result["checks"]["route"]["status"] == "not_applicable"


def test_malformed_route_rows_are_unknown():
    result = check_gateway_current(DESIRED, [{"gateway": "192.0.2.1"}, "bad"], GATEWAY_ROWS)

    assert result["status"] == "unsupported"
    assert result["current_status"] == "verified"
    assert result["checks"]["route"]["status"] == "not_applicable"


def test_incomplete_search_gateway_page_does_not_report_gateway_absent():
    page = deepcopy(GATEWAY_ROWS)
    page["total"] = 2
    page["rows"] = [{"name": "OTHER", "interface": "lan", "if": "igc1", "gateway": "198.51.100.1",
                     "monitor": "198.51.100.1", "monitor_disable": False, "status": "Online"}]
    result = check_gateway_current(DESIRED, ROUTES, page)

    assert result["status"] == "unknown"
    assert result["reason"] == "gateway_status_page_incomplete"


def test_incomplete_search_gateway_page_does_not_verify_matching_gateway():
    page = deepcopy(GATEWAY_ROWS)
    page["total"] = 2
    result = check_gateway_current(DESIRED, ROUTES, page, {"status": "not_applicable"})

    assert result["status"] == "unknown"
    assert result["reason"] == "gateway_status_page_incomplete"


class GatewayAdapter(FixedCollectionTransport):
    def __init__(self, *, version="26.7.3", routes=None, total=1, consumers=None,
                 pf_snapshot=None, monitor=None):
        super().__init__(TARGET, CREDENTIALS)
        self.version = version
        self.routes = routes if routes is not None else []
        self.total = total
        self.consumers = consumers if consumers is not None else []
        self.pf_snapshot = pf_snapshot if pf_snapshot is not None else {
            "rules": {"filter rules": {}, "nat rules": {}},
        }
        self.monitor = monitor
        self.calls = []

    def _request(self, method, path, payload=None):
        self.calls.append((method, path, deepcopy(payload)))
        if method == "GET" and path == "core/firmware/status":
            return {"product": {"product_version": self.version}}
        if method == "POST" and path == "routing/settings/search_gateway":
            rows = GATEWAY_ROWS["rows"] if payload["current"] == 1 else []
            if self.monitor is not None:
                rows = deepcopy(rows)
                for row in rows:
                    row["monitor"] = self.monitor
            return {"current": payload["current"], "rowCount": payload["rowCount"],
                    "total": self.total, "rows": deepcopy(rows)}
        if method == "GET" and path == "diagnostics/interface/get_routes":
            return deepcopy(self.routes)
        if method == "GET" and path == "firewall/filter/get":
            return {"filter": {"rules": {"rule": deepcopy(self.consumers)}}}
        if method == "GET" and path == "diagnostics/firewall/pf_statistics/rules":
            return deepcopy(self.pf_snapshot)
        raise AssertionError((method, path, payload))


def test_transport_gateway_observation_preserves_runtime_fields_and_reads_explicit_host_route():
    adapter = GatewayAdapter(routes=[{
        "destination": "198.51.100.10", "gateway": "192.0.2.1", "netif": "igc0",
    }], monitor="198.51.100.10")
    desired = deepcopy(DESIRED)
    desired["monitor"] = "198.51.100.10"
    desired["monitor_noroute"] = False
    result = Reader(TARGET, CREDENTIALS, adapter).active_check(
        "gateways", ["WAN", "192.0.2.1"], desired,
        context={"route_expectation": {"purpose": "monitor_host", "destination": "192.0.2.1/32"},
                 "consumer_observation": {"status": "not_applicable"}},
    )

    assert result["status"] == "verified"
    assert result["checks"]["runtime_status"]["observed"] == "Online"
    assert result["checks"]["runtime_status"]["status"] == "not_applicable"
    assert result["checks"]["route"]["status"] == "verified"
    assert result["coverage"]["gateway_status"]["complete"] is True
    assert [call[1] for call in adapter.calls] == [
        "core/firmware/status", "routing/settings/search_gateway", "firewall/filter/get",
        "diagnostics/firewall/pf_statistics/rules", "diagnostics/interface/get_routes",
    ]


def test_transport_gateway_observation_does_not_read_routes_without_explicit_route_purpose():
    adapter = GatewayAdapter()
    desired = deepcopy(DESIRED)
    desired["monitor_noroute"] = False
    result = Reader(TARGET, CREDENTIALS, adapter).active_check(
        "gateways", ["WAN", "192.0.2.1"], desired,
        context={"consumer_observation": {"status": "not_applicable"}},
    )

    assert result["status"] == "verified"
    assert result["checks"]["route"]["status"] == "not_applicable"
    assert "diagnostics/interface/get_routes" not in [call[1] for call in adapter.calls]
    assert "firewall/filter/get" in [call[1] for call in adapter.calls]


def test_transport_gateway_observation_verifies_loaded_route_to_by_native_uuid():
    uuid = "11111111-1111-4111-8111-111111111111"
    raw_rule = f'@4 pass in quick on igc0 route-to ( igc0 192.0.2.1 ) inet proto tcp from any to any label "{uuid}"'
    adapter = GatewayAdapter(
        routes=[{"destination": "198.51.100.10", "gateway": "192.0.2.1", "netif": "igc0"}],
        consumers=[{"uuid": uuid, "gateway": "WAN", "interface": ["wan"], "enabled": True}],
        pf_snapshot={"rules": {"filter rules": {raw_rule: {}}, "nat rules": {}}},
        monitor="198.51.100.10",
    )
    desired = deepcopy(DESIRED)
    desired["monitor"] = "198.51.100.10"
    desired["monitor_noroute"] = False
    result = Reader(TARGET, CREDENTIALS, adapter).active_check(
        "gateways", ["WAN", "192.0.2.1"], desired,
    )

    assert result["status"] == "verified"
    assert result["consumer"]["status"] == "verified"
    assert result["checks"]["route"]["status"] == "verified"


def test_transport_gateway_observation_requires_complete_page_before_matching_row():
    adapter = GatewayAdapter(total=2)
    result = Reader(TARGET, CREDENTIALS, adapter).active_check(
        "gateways", ["WAN", "192.0.2.1"], DESIRED,
        context={"consumer_observation": {"status": "not_applicable"}},
    )

    assert result["status"] == "unknown"
    assert result["reason"] == "gateway_configuration_incomplete"
