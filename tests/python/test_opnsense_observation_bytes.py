"""Regression checks for the per-observation OPNsense HTTP byte budget."""

from __future__ import annotations

import json
from collections.abc import Mapping
from urllib.parse import urlsplit

import pytest

import iaas_automation.opnsense_workflow.reader as reader_module
from iaas_automation.opnsense_workflow.reader import (
    FixedCollectionTransport,
    Reader,
)


TARGET = {"host": "firewall", "endpoint": "https://firewall.example", "ssl_verify": True}
CREDENTIALS = {"OPNSENSE_API_KEY": "key", "OPNSENSE_API_SECRET": "secret"}


def _body(value: object) -> bytes:
    return json.dumps(value, separators=(",", ":")).encode()


class FakeResponse:
    status_code = 200

    def __init__(self, body: bytes, closed: list[bool]) -> None:
        self.body = body
        self.closed = closed

    def iter_content(self, chunk_size: int):
        del chunk_size
        midpoint = max(1, len(self.body) // 2)
        yield self.body[:midpoint]
        yield self.body[midpoint:]

    def close(self) -> None:
        self.closed.append(True)


class FakeSession:
    """Small requests.Session-shaped router that records streamed body sizes."""

    def __init__(self, routes: Mapping[str, bytes | list[bytes]]) -> None:
        self.routes = dict(routes)
        self.indexes = {path: 0 for path in routes}
        self.calls: list[tuple[str, str, int]] = []
        self.closed: list[bool] = []
        self.auth = None
        self.verify = None

    def request(self, method: str, url: str, **kwargs: object) -> FakeResponse:
        del kwargs
        path = urlsplit(url).path.split("/api/", 1)[1]
        route = self.routes[path]
        if isinstance(route, list):
            index = self.indexes[path]
            body = route[min(index, len(route) - 1)]
            self.indexes[path] = index + 1
        else:
            body = route
        self.calls.append((method, path, len(body)))
        return FakeResponse(body, self.closed)

    def close(self) -> None:
        pass


def _reader(session: FakeSession) -> Reader:
    transport = FixedCollectionTransport(TARGET, CREDENTIALS, session=session)
    return Reader(TARGET, CREDENTIALS, transport)


def _common_routes() -> dict[str, bytes]:
    return {"firewall/group/get_item": _body({"group": {"members": {"lan": {"selected": 1}}}})}


def _alias_body(description: str = "managed") -> bytes:
    return _body({"alias": {"aliases": {"alias": [{
        "name": "A", "type": "host", "content": ["192.0.2.1"],
        "description": description, "enabled": True,
    }]}}})


def _vip_body(description: str = "vip") -> bytes:
    return _body({"vip": {"vip": [{
        "description": description, "interface": "lan", "address": "192.0.2.10/32",
        "bind": False, "expand": True,
    }]}})


def test_reused_reader_budget_is_per_read_and_not_transport_lifetime(monkeypatch: pytest.MonkeyPatch) -> None:
    routes = _common_routes() | {"firewall/alias/get": _alias_body()}
    session = FakeSession(routes)
    reader = _reader(session)
    # The fixed reader makes two requests per selected resource.  Use the
    # actual encoded size so the test remains small while retaining the real
    # streaming and cumulative accounting path.
    one_round = len(routes["firewall/group/get_item"]) + len(routes["firewall/alias/get"])
    monkeypatch.setattr(reader_module, "MAX_TOTAL_BYTES", one_round + 1)

    for _ in range(2):
        observation = reader.read(["aliases"])["aliases"]
        assert observation["status"] == "complete"

    assert one_round < reader_module.MAX_TOTAL_BYTES
    assert sum(size for _, _, size in session.calls) > reader_module.MAX_TOTAL_BYTES
    assert len(session.closed) == len(session.calls)


def test_one_read_shares_limit_across_resources_and_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    routes = _common_routes() | {
        "firewall/alias/get": _alias_body(),
        "interfaces/vip_settings/get": _vip_body(),
    }
    session = FakeSession(routes)
    reader = _reader(session)
    first_resource = len(routes["firewall/group/get_item"]) + len(routes["firewall/alias/get"])
    second_resource = len(routes["firewall/group/get_item"]) + len(routes["interfaces/vip_settings/get"])
    monkeypatch.setattr(reader_module, "MAX_TOTAL_BYTES", first_resource + second_resource - 1)

    observations = reader.read(["aliases", "vips"])

    assert observations["aliases"]["status"] == "complete"
    assert observations["vips"]["status"] == "unsupported"
    assert observations["vips"]["reason"] == "response_bound_exceeded"
    assert max(size for _, _, size in session.calls) < reader_module.MAX_TOTAL_BYTES


def test_one_paged_read_exceeding_total_limit_never_reports_complete(monkeypatch: pytest.MonkeyPatch) -> None:
    gateway_one = {
        "name": "WAN", "interface": "wan", "ip_protocol": "inet", "gateway": "192.0.2.1",
        "default_gw": False, "far_gw": False, "monitor_disable": False, "monitor_noroute": False,
        "monitor": "192.0.2.1", "force_down": False, "latency_low": 200, "latency_high": 500,
        "loss_low": 10, "loss_high": 20, "interval": 1, "time_period": 60,
        "loss_interval": 4, "data_length": 1, "priority": 255, "weight": 1, "description": "managed",
    }
    gateway_two = gateway_one | {"name": "WAN2", "gateway": "192.0.2.2"}
    routes: dict[str, bytes | list[bytes]] = _common_routes() | {
        "routing/settings/search_gateway": [
            _body({"current": 1, "rowCount": 1, "total": 2, "rows": [{"uuid": "gw-1"}]}),
            _body({"current": 2, "rowCount": 1, "total": 2, "rows": [{"uuid": "gw-2"}]}),
        ],
        "routing/settings/get_gateway/gw-1": _body({"gateway_item": gateway_one}),
        "routing/settings/get_gateway/gw-2": _body({"gateway_item": gateway_two}),
    }
    session = FakeSession(routes)
    reader = _reader(session)
    all_responses = sum(
        len(body) if isinstance(body, bytes) else sum(len(item) for item in body)
        for body in routes.values()
    )
    monkeypatch.setattr(reader_module, "MAX_TOTAL_BYTES", all_responses - 1)

    observation = reader.read(["gateways"])["gateways"]

    assert observation["status"] == "unsupported"
    assert observation["reason"] == "response_bound_exceeded"
    assert observation["objects"] == []
    assert max(size for _, _, size in session.calls) < reader_module.MAX_TOTAL_BYTES


def test_new_read_recovers_after_previous_read_exceeded_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    small = _alias_body()
    large = _alias_body("managed" + "x" * 700)
    routes = _common_routes() | {"firewall/alias/get": [large, small]}
    session = FakeSession(routes)
    reader = _reader(session)
    limit = len(routes["firewall/group/get_item"]) + len(small) + 1
    monkeypatch.setattr(reader_module, "MAX_TOTAL_BYTES", limit)

    first = reader.read(["aliases"])["aliases"]
    second = reader.read(["aliases"])["aliases"]

    assert first["status"] == "unsupported"
    assert first["reason"] == "response_bound_exceeded"
    assert second["status"] == "complete"
    assert second["objects"][0]["identity"] == ["A"]


def test_multistage_apply_retains_unknown_recovery_after_readback_failure(tmp_path) -> None:
    """Reuse the workflow fixture to keep a failed bounded read recoverable."""
    from test_opnsense_workflow import Appliance, alias, candidate, documents, execute, rule

    class FailingAfterSave(Appliance):
        def save(self, resource, records):
            result = super().save(resource, records)
            self.unreadable = True
            return result

    device = FailingAfterSave()
    cand = candidate(device, documents(aliases=[alias()], filter_rules=[rule()]))
    assert len(cand["stages"]) >= 2

    result = execute(tmp_path, device, cand)

    assert result["status"] == "failed"
    assert device.calls == [("save", "aliases")]
    recovery = json.loads((tmp_path / "recovery.json").read_text())
    assert recovery["stages"][0]["attempted"] is True
    assert all(entry["after_status"] == "unknown" for entry in recovery["entries"])


@pytest.mark.parametrize('fail_observation', [False, True])
def test_real_reader_multistage_apply_and_failure_recovery(monkeypatch, tmp_path, fail_observation):
    from copy import deepcopy
    from test_opnsense_workflow import Appliance, TARGET as WORKFLOW_TARGET, alias, candidate, documents, rule
    from iaas_automation.opnsense_workflow.contracts import identity
    from iaas_automation.opnsense_workflow.executor import apply

    limit = 2000
    monkeypatch.setattr(reader_module, 'MAX_TOTAL_BYTES', limit)
    routes = _common_routes() | {
        'firewall/alias/get': _body({'alias': {'aliases': {'alias': []}}}),
        'firewall/filter/get': _body({'filter': {'rules': {'rule': []}}}),
        'interfaces/vip_settings/get': _body({'vip': {'vip': []}}),
        'firewall/d_nat/get': _body({'DNat': {'rule': []}}),
        'firewall/one_to_one/get': _body({'filter': {'onetoone': {'rule': []}}}),
        'firewall/group/get': _body({'group': {'ifgroupentry': []}}),
        'routing/settings/search_gateway': _body({'current': 1, 'rowCount': 0, 'total': 0, 'rows': []}),
    }
    session = FakeSession(routes)
    reader = Reader(WORKFLOW_TARGET, CREDENTIALS,
                    FixedCollectionTransport(WORKFLOW_TARGET, CREDENTIALS, session=session))

    class Writer(Appliance):
        def save(self, resource, records):
            result = super().save(resource, records)
            rows = deepcopy(self.resources[resource])
            for row in rows:
                if resource == 'filter-rules':
                    row['description'] = identity(resource, row)[0]
                    row.pop('scope')
                    row.pop('slug')
                row.pop('state')
            if resource == 'aliases':
                session.routes['firewall/alias/get'] = _body({'alias': {'aliases': {'alias': rows}}})
            else:
                session.routes['firewall/filter/get'] = _body({'filter': {'rules': {'rule': rows}}})
            return result

        def activate(self, resource):
            result = super().activate(resource)
            if fail_observation and resource == 'aliases':
                body = session.routes['firewall/alias/get']
                session.routes['firewall/alias/get'] = [b' ' * limit + body, body]
            return result

    writer = Writer()
    cand = candidate(reader, documents(aliases=[alias()], filter_rules=[rule(enabled=False)]))
    result = apply(cand, 'a' * 64, reader, writer, 'test-budget', {
        'target': WORKFLOW_TARGET, 'candidate_sha256': 'a' * 64, 'execution_id': 'test-budget',
        'checked_no_pending': True, 'serialized': True,
    }, tmp_path)

    assert result['status'] == ('failed' if fail_observation else 'fully_verified')
    assert writer.calls == ([('save', 'aliases'), ('activate', 'aliases')] if fail_observation else [
        ('save', 'aliases'), ('activate', 'aliases'), ('save', 'filter-rules'), ('activate', 'filter-rules')])
    recovery = json.loads((tmp_path / 'recovery.json').read_text())
    assert all(entry['after_status'] == 'confirmed' for entry in recovery['entries'])
    assert sum(size for _, _, size in session.calls) > limit
    assert len(session.closed) == len(session.calls)
