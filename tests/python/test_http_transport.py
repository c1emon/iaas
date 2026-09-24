"""Offline contracts for the bounded HTTP read helper."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any, cast

import pytest
import requests

from iaas.http_transport import HttpResponse, ReadBudget, TransportFailure, read_json

pytestmark = pytest.mark.fast


class Response:
    def __init__(self, chunks: list[object], *, status_code: int = 200) -> None:
        self.chunks = chunks
        self.status_code = status_code
        self.closed = False
        self.chunk_size: int | None = None

    @property
    def content(self) -> bytes:
        return b"".join(chunk for chunk in self.chunks if isinstance(chunk, bytes))

    def iter_content(self, chunk_size: int) -> Iterator[object]:
        self.chunk_size = chunk_size
        yield from self.chunks

    def close(self) -> None:
        self.closed = True


class Session:
    def __init__(self, responses: list[Response]) -> None:
        self.responses = responses
        self.calls: list[tuple[str, str, dict[str, Any]]] = []

    def request(self, method: str, url: str, **kwargs: Any) -> HttpResponse:
        self.calls.append((method, url, kwargs))
        return cast(HttpResponse, self.responses[len(self.calls) - 1])


def test_read_json_preserves_fixed_request_shape_and_decodes_once() -> None:
    response = Response([b'{"ok":true}'])
    session = Session([response])
    budget = ReadBudget()

    assert read_json(
        session,
        "POST",
        "https://example.invalid/api/query",
        verify=False,
        budget=budget,
        json_body={"current": 1},
    ) == {"ok": True}

    method, url, kwargs = session.calls[0]
    assert (method, url) == ("POST", "https://example.invalid/api/query")
    assert kwargs["json"] == {"current": 1}
    assert kwargs["verify"] is False
    assert kwargs["timeout"] == (5.0, 15.0)
    assert kwargs["allow_redirects"] is False
    assert kwargs["stream"] is True
    assert response.chunk_size == 8192
    assert response.closed
    assert budget.used_bytes == len(b'{"ok":true}')


def test_http_failure_keeps_status_and_closes_response_without_retry() -> None:
    response = Response([b"{}"], status_code=503)
    session = Session([response])

    with pytest.raises(TransportFailure) as caught:
        read_json(session, "GET", "https://example.invalid/api/query", verify=True, budget=ReadBudget())

    assert caught.value.reason == "http_failure"
    assert caught.value.status_code == 503
    assert len(session.calls) == 1
    assert response.closed


def test_stream_failure_is_classified_without_backend_text() -> None:
    class BrokenResponse(Response):
        def iter_content(self, chunk_size: int) -> Iterator[object]:
            self.chunk_size = chunk_size
            raise requests.ConnectionError("private-backend-token")
            yield b"unreachable"

    response = BrokenResponse([])
    session = Session([response])

    with pytest.raises(TransportFailure) as caught:
        read_json(session, "GET", "https://example.invalid/api/query", verify=True, budget=ReadBudget())

    assert caught.value.reason == "transport_failure"
    assert "private-backend-token" not in str(caught.value)
    assert response.closed


def test_malformed_chunks_and_json_are_distinct_and_close() -> None:
    response = Response(["not bytes"])
    with pytest.raises(TransportFailure, match="malformed_response_body") as caught:
        read_json(Session([response]), "GET", "https://example.invalid/api/query", verify=True, budget=ReadBudget())
    assert caught.value.reason == "malformed_response_body"
    assert response.closed

    invalid_json = Response([b"not-json"])
    with pytest.raises(TransportFailure, match="malformed_json") as caught:
        read_json(Session([invalid_json]), "GET", "https://example.invalid/api/query", verify=True, budget=ReadBudget())
    assert caught.value.reason == "malformed_json"
    assert invalid_json.closed


def test_cumulative_bytes_are_not_reset_between_requests() -> None:
    first = Response([b"{}"])  # 2 bytes
    second = Response([b"{}"])  # 2 more bytes, beyond a 3-byte total
    session = Session([first, second])
    budget = ReadBudget(max_response_bytes=2, max_total_bytes=3)

    assert read_json(session, "GET", "https://example.invalid/api/one", verify=True, budget=budget) == {}
    with pytest.raises(TransportFailure, match="response_bound_exceeded") as caught:
        read_json(session, "GET", "https://example.invalid/api/two", verify=True, budget=budget)

    assert caught.value.reason == "response_bound_exceeded"
    assert budget.used_bytes == 4
    assert first.closed and second.closed


def test_deadline_clamps_timeout_and_is_checked_during_stream() -> None:
    now = [0.0]

    def clock() -> float:
        return now[0]

    class SlowResponse(Response):
        def iter_content(self, chunk_size: int):
            self.chunk_size = chunk_size
            yield b"{"
            now[0] = 2.0
            yield b"}"

    response = SlowResponse([])
    session = Session([response])
    budget = ReadBudget(deadline=2.0, clock=clock)

    with pytest.raises(TransportFailure, match="observation_deadline_exhausted") as caught:
        read_json(session, "GET", "https://example.invalid/api/query", verify=True, budget=budget)

    assert caught.value.reason == "observation_deadline_exhausted"
    timeout = session.calls[0][2]["timeout"]
    assert timeout.total == timeout.connect_timeout == 2.0
    assert response.closed


@pytest.mark.parametrize(
    "kwargs",
    [
        {"max_response_bytes": 0},
        {"max_total_bytes": 0},
        {"used_bytes": -1},
        {"request_timeout_seconds": 16},
    ],
)
def test_budget_rejects_invalid_limits(kwargs: dict[str, Any]) -> None:
    with pytest.raises(ValueError):
        ReadBudget(**kwargs)


def test_non_standard_json_constant_is_rejected_without_backend_cause() -> None:
    response = Response([b'{"value": NaN}'])
    with pytest.raises(TransportFailure, match='malformed_json') as caught:
        read_json(Session([response]), 'GET', 'https://example.invalid/api/query', verify=True, budget=ReadBudget())
    assert caught.value.__cause__ is None
    assert response.closed
