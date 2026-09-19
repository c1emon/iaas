from __future__ import annotations

import pytest

from iaas_automation.opnsense_workflow.confirmation import complete_action
from iaas_automation.opnsense_workflow.reader import FixedCollectionTransport, observation_budget


TARGET = {"endpoint": "https://192.0.2.254", "ssl_verify": True}
CREDENTIALS = {"OPNSENSE_API_KEY": "key", "OPNSENSE_API_SECRET": "secret"}


class Clock:
    def __init__(self) -> None:
        self.value = 0.0

    def now(self) -> float:
        return self.value


class Response:
    status_code = 200

    def __init__(self, chunks, close):
        self._chunks = chunks
        self._close = close

    def iter_content(self, size):
        yield from self._chunks

    def close(self):
        self._close.append(True)


class Session:
    def __init__(self, response):
        self.response = response
        self.calls = []
        self.verify = None
        self.auth = None

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        return self.response


def transport(session):
    return FixedCollectionTransport(TARGET, CREDENTIALS, session=session)


def test_request_timeout_and_stream_are_bound_by_shared_budget() -> None:
    clock = Clock()
    closed = []
    session = Session(Response([b"{}"], closed))
    client = transport(session)

    with observation_budget(3, clock=clock.now):
        assert client._request("GET", "firewall/alias/get") == {}

    timeout = session.calls[0][2]["timeout"]
    assert timeout.total == timeout.connect_timeout == 3.0
    assert closed == [True]


def test_stream_expiry_is_unknown_and_closes_response() -> None:
    clock = Clock()
    closed = []

    def chunks():
        yield b"{"
        clock.value = 2
        yield b"}"

    session = Session(Response(chunks(), closed))
    client = transport(session)
    with observation_budget(2, clock=clock.now):
        with pytest.raises(RuntimeError, match="observation_deadline_exhausted"):
            client._request("GET", "firewall/alias/get")
    assert closed == [True]


def test_complete_action_recomputes_timeout_after_boundary() -> None:
    clock = Clock()
    observed = []

    class Device:
        def observe_confirmation(self, stage, action_id, *, timeout):
            observed.append(timeout)
            return {"status": "confirmed", "complete": True, "fresh": True, "action_id": action_id}

    def boundary():
        clock.value = 4

    stage = {"confirmation": {"wait": {
        "deadline_seconds": 5, "max_attempts": 2, "request_timeout_seconds": 10, "interval_seconds": 0,
    }}}
    result = complete_action(stage, {"status": "processing", "action_id": "a-1"}, Device(), boundary,
                             clock=clock.now, sleep=lambda seconds: None)

    assert result["status"] == "confirmed"
    assert observed == [1.0]


def test_custom_transport_without_budget_support_is_unknown() -> None:
    class Device:
        transport = object()

        def observe_confirmation(self, stage, action_id, *, timeout):
            raise AssertionError("unsupported transport must not be queried")

    stage = {"confirmation": {"wait": {
        "deadline_seconds": 5, "max_attempts": 1, "request_timeout_seconds": 1, "interval_seconds": 0,
    }}}
    result = complete_action(stage, {"status": "processing", "action_id": "a-1"}, Device(), lambda: None)
    assert result["status"] == "unknown"
    assert result["reason"] == "bounded_reader_unavailable"
