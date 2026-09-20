"""Bounded response handling for fixed, read-only HTTP adapters.

The caller owns endpoint admission, authentication, session construction and
session cleanup.  This module performs exactly one already-approved request
and owns cleanup of the response returned by that request.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
import json
import math
import time
from typing import Any, NoReturn, Protocol, cast

import requests
from urllib3.util import Timeout

from iaas_automation.common.errors import Diagnostic


DEFAULT_MAX_RESPONSE_BYTES = 2 * 1024 * 1024
DEFAULT_MAX_TOTAL_BYTES = 8 * 1024 * 1024
DEFAULT_REQUEST_TIMEOUT_SECONDS = 15.0
_CONNECT_TIMEOUT_SECONDS = 5.0
_READ_CHUNK_SIZE = 8192


class HttpResponse(Protocol):
    """The response surface required from requests or a test double."""

    status_code: int
    @property
    def content(self) -> bytes:
        ...

    def iter_content(self, chunk_size: int) -> Iterable[object]:
        ...

    def close(self) -> None:
        ...


class HttpSession(Protocol):
    """The minimal session surface required by :func:`read_json`."""

    def request(self, method: str, url: str, **kwargs: Any) -> HttpResponse:
        ...


@dataclass(kw_only=True)
class ReadBudget:
    """Mutable byte limits and optional cooperative deadline for one scope.

    ``used_bytes`` is intentionally mutable so an adapter can seed a budget
    from its existing instance counter and copy the value back in ``finally``
    even when the current response exceeds a bound.
    """

    used_bytes: int = 0
    max_response_bytes: int = DEFAULT_MAX_RESPONSE_BYTES
    max_total_bytes: int = DEFAULT_MAX_TOTAL_BYTES
    deadline: float | None = None
    clock: Callable[[], float] = time.monotonic
    request_timeout_seconds: float = DEFAULT_REQUEST_TIMEOUT_SECONDS

    def __post_init__(self) -> None:
        for name, value in (
            ("used_bytes", self.used_bytes),
            ("max_response_bytes", self.max_response_bytes),
            ("max_total_bytes", self.max_total_bytes),
        ):
            if type(value) is not int or value < 0:
                raise ValueError(f"{name} must be a non-negative integer")
        if self.max_response_bytes == 0 or self.max_total_bytes == 0:
            raise ValueError("byte limits must be greater than zero")
        if self.deadline is not None and (
            isinstance(self.deadline, bool)
            or not isinstance(self.deadline, (int, float))
            or not math.isfinite(float(self.deadline))
        ):
            raise ValueError("deadline must be a finite number")
        if (
            isinstance(self.request_timeout_seconds, bool)
            or not isinstance(self.request_timeout_seconds, (int, float))
            or not 0 < float(self.request_timeout_seconds) <= DEFAULT_REQUEST_TIMEOUT_SECONDS
            or not math.isfinite(float(self.request_timeout_seconds))
        ):
            raise ValueError("request timeout must be within the fixed limit")
        if not callable(self.clock):
            raise ValueError("clock must be callable")

    def remaining(self) -> float | None:
        """Return remaining cooperative seconds, or ``None`` if unbounded."""

        if self.deadline is None:
            return None
        return max(0.0, self.deadline - float(self.clock()))

    def timeout(self) -> tuple[float, float] | Timeout:
        """Build the fixed request timeout, clamped to the deadline."""

        remaining = self.remaining()
        if remaining is None:
            return (_CONNECT_TIMEOUT_SECONDS, DEFAULT_REQUEST_TIMEOUT_SECONDS)
        timeout_seconds = min(remaining, float(self.request_timeout_seconds))
        if timeout_seconds <= 0:
            raise TransportFailure("observation_deadline_exhausted")
        return Timeout(
            total=timeout_seconds,
            connect=min(_CONNECT_TIMEOUT_SECONDS, timeout_seconds),
            read=min(DEFAULT_REQUEST_TIMEOUT_SECONDS, timeout_seconds),
        )


class TransportFailure(RuntimeError):
    """Safe, adapter-neutral failure from one bounded request."""

    def __init__(self, reason: str, status_code: int | None = None) -> None:
        safe_status = status_code if type(status_code) is int and 100 <= status_code <= 599 else None
        self.diagnostic = Diagnostic("http_transport", reason, status_code=safe_status)
        super().__init__(reason)
        self.reason = reason
        self.status_code = status_code


def _reject_json_constant(value: str) -> NoReturn:
    del value
    raise ValueError("non-standard JSON constant")


def _chunks(response: requests.Response | HttpResponse) -> Iterable[object]:
    iterator = cast(Callable[[int], Iterable[object]] | None, getattr(response, "iter_content", None))
    if callable(iterator):
        return iterator(_READ_CHUNK_SIZE)
    return [response.content]


def _close(response: requests.Response | HttpResponse) -> None:
    try:
        response.close()
    except Exception:
        # Closing is best effort; it must not replace the classified result of
        # the bounded read or expose backend details from a test/HTTP object.
        pass


def read_json(
    session: requests.Session | HttpSession,
    method: str,
    url: str,
    *,
    verify: bool,
    budget: ReadBudget,
    params: Mapping[str, Any] | None = None,
    json_body: Mapping[str, Any] | None = None,
) -> Any:
    """Issue one bounded request and decode its strict JSON response.

    The endpoint and payload must already have been admitted by the caller.
    HTTP status interpretation remains with that caller; this helper reports
    all non-2xx responses as ``http_failure`` with the numeric status code.
    """

    if method not in {"GET", "POST"}:
        raise ValueError("bounded read transport supports GET and POST only")
    if type(verify) is not bool:
        raise ValueError("verify must be a boolean")

    response: requests.Response | HttpResponse | None = None
    try:
        if (remaining := budget.remaining()) is not None and remaining <= 0:
            raise TransportFailure("observation_deadline_exhausted")
        kwargs: dict[str, Any] = {
            "verify": verify,
            "timeout": budget.timeout(),
            "allow_redirects": False,
            "stream": True,
        }
        if method == "GET" and params is not None:
            kwargs["params"] = params
        if method == "POST" and json_body is not None:
            kwargs["json"] = json_body
        response = session.request(method, url, **kwargs)

        if (remaining := budget.remaining()) is not None and remaining <= 0:
            raise TransportFailure("observation_deadline_exhausted")
        if not 200 <= response.status_code < 300:
            raise TransportFailure("http_failure", response.status_code)

        body = bytearray()
        try:
            for chunk in _chunks(response):
                if (remaining := budget.remaining()) is not None and remaining <= 0:
                    raise TransportFailure("observation_deadline_exhausted")
                if not isinstance(chunk, (bytes, bytearray)):
                    raise TransportFailure("malformed_response_body")
                body.extend(chunk)
                budget.used_bytes += len(chunk)
                if len(body) > budget.max_response_bytes or budget.used_bytes > budget.max_total_bytes:
                    raise TransportFailure("response_bound_exceeded")
            if (remaining := budget.remaining()) is not None and remaining <= 0:
                raise TransportFailure("observation_deadline_exhausted")
        except TransportFailure:
            raise
        except requests.Timeout:
            raise TransportFailure("timeout") from None
        except requests.RequestException:
            raise TransportFailure("transport_failure") from None
        except (TypeError, ValueError, UnicodeError):
            raise TransportFailure("malformed_response_body") from None
        try:
            decoded = json.loads(bytes(body), parse_constant=_reject_json_constant)
        except (ValueError, UnicodeError):
            raise TransportFailure("malformed_json") from None
        if (remaining := budget.remaining()) is not None and remaining <= 0:
            raise TransportFailure("observation_deadline_exhausted")
        return decoded
    except requests.Timeout:
        raise TransportFailure("timeout") from None
    except requests.RequestException:
        raise TransportFailure("transport_failure") from None
    finally:
        if response is not None:
            _close(response)
