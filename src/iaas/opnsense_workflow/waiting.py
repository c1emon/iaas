"""Bounded, read-only completion observation.

The workflow submits an activation or content action elsewhere.  This module
only polls a fixed read callback after that submission; it never accepts an
endpoint, a writer, or an operation to retry.  The callback receives the
request timeout available for that observation and returns one complete
observation mapping.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import math
from typing import Any, Callable, Mapping, Protocol
import time


class ReadOnlyCallback(Protocol):
    """One bounded read of the already selected completion evidence."""

    def __call__(self, timeout: float) -> Mapping[str, Any]:
        ...


Clock = Callable[[], float]
Sleeper = Callable[[float], None]


@dataclass(frozen=True)
class WaitPolicy:
    """Limits reviewed with a candidate before an observation wait starts."""

    deadline_seconds: float = 60.0
    max_attempts: int = 30
    request_timeout_seconds: float = 15.0
    interval_seconds: float = 2.0

    def __post_init__(self) -> None:
        for name in ("deadline_seconds", "request_timeout_seconds", "interval_seconds"):
            value = getattr(self, name)
            if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value):
                raise ValueError(f"{name} must be finite")
        if self.deadline_seconds <= 0:
            raise ValueError("deadline_seconds must be greater than zero")
        if type(self.max_attempts) is not int or self.max_attempts <= 0:
            raise ValueError("max_attempts must be a positive integer")
        if self.request_timeout_seconds <= 0:
            raise ValueError("request_timeout_seconds must be greater than zero")
        if self.interval_seconds < 0:
            raise ValueError("interval_seconds must not be negative")


@dataclass(frozen=True)
class WaitResult:
    """The bounded wait outcome and the last complete observation, if any."""

    status: str
    reason: str
    attempts: int
    elapsed_seconds: float
    last_observation: dict[str, Any] | None

    def as_dict(self) -> dict[str, Any]:
        """Return the result in the workflow's existing mapping style."""

        return {
            "status": self.status,
            "reason": self.reason,
            "attempts": self.attempts,
            "elapsed_seconds": self.elapsed_seconds,
            "last_observation": deepcopy(self.last_observation),
        }


_CONFIRMED = {"confirmed"}
_FAILED = {"failed", "failure", "error"}
_PROCESSING = {"processing"}
_UNKNOWN_TERMINAL = {
    "accepted", "canceled", "cancelled", "incomplete", "pending", "timeout", "unknown", "unconfirmed",
    "unsupported",
}


def _snapshot(observation: Mapping[str, Any]) -> dict[str, Any]:
    """Copy provider data so a later callback cannot rewrite the retained fact."""

    return deepcopy(dict(observation))


def _result(status: str, reason: str, attempts: int, started: float, now: float,
            last_observation: dict[str, Any] | None) -> WaitResult:
    return WaitResult(status, reason, attempts, max(0.0, now - started), last_observation)


def wait_for_confirmation(
    read: ReadOnlyCallback,
    *,
    policy: WaitPolicy | None = None,
    clock: Clock = time.monotonic,
    sleep: Sleeper = time.sleep,
) -> WaitResult:
    """Poll fixed completion evidence within a reviewed bounded policy.

    ``read`` is called at most ``policy.max_attempts`` times.  Its timeout is
    the smaller of the policy request timeout and the remaining monotonic
    deadline, so a provider request cannot extend the stage's total wait.
    Explicit failure, cancellation, request timeout and unreadable responses
    terminate with an honest result.  Only processing observations are polled
    again; no write, activation, reload, or content refresh is retried here.
    """

    if not callable(read):
        raise TypeError("read must be callable")
    if not callable(clock) or not callable(sleep):
        raise TypeError("clock and sleep must be callable")
    policy = policy or WaitPolicy()

    started = clock()
    deadline = started + policy.deadline_seconds
    attempts = 0
    last_observation: dict[str, Any] | None = None

    while attempts < policy.max_attempts:
        now = clock()
        remaining = deadline - now
        if remaining <= 0:
            return _result("unknown", "deadline", attempts, started, now, last_observation)

        request_timeout = min(policy.request_timeout_seconds, remaining)
        attempts += 1
        try:
            observation = read(request_timeout)
        except (TimeoutError,):
            return _result("unknown", "request_timeout", attempts, started, clock(), last_observation)
        except Exception as exc:
            if exc.__class__.__name__ in {"CancelledError", "CanceledError"}:
                return _result("unknown", "cancelled", attempts, started, clock(), last_observation)
            return _result("unknown", "unreadable", attempts, started, clock(), last_observation)
        except BaseException as exc:
            # asyncio.CancelledError inherits BaseException on supported
            # Python versions; do not swallow unrelated process interrupts.
            if exc.__class__.__name__ in {"CancelledError", "CanceledError"}:
                return _result("unknown", "cancelled", attempts, started, clock(), last_observation)
            raise

        if not isinstance(observation, Mapping):
            return _result("unknown", "unreadable", attempts, started, clock(), last_observation)
        last_observation = _snapshot(observation)
        observed_at = clock()
        if observed_at > deadline:
            return _result("unknown", "deadline", attempts, started, observed_at, last_observation)

        state = observation.get("status")
        if not isinstance(state, str):
            return _result("unknown", "unreadable", attempts, started, observed_at, last_observation)
        state = state.lower()
        if state in _CONFIRMED:
            if (observation.get("complete") is not True or observation.get("fresh") is not True
                    or observation.get("truncated") is True):
                return _result("unknown", "incomplete_evidence", attempts, started, observed_at, last_observation)
            return _result("confirmed", "completed", attempts, started, observed_at, last_observation)
        if state in _FAILED:
            return _result("failed", "explicit_failure", attempts, started, observed_at, last_observation)
        if state in _UNKNOWN_TERMINAL:
            if state in {"cancelled", "canceled"}:
                reason = "cancelled"
            elif state == "timeout":
                reason = "request_timeout"
            elif state in {"accepted", "pending", "unconfirmed"}:
                reason = "unconfirmed"
            elif state == "unknown":
                reason = "unknown"
            elif state == "incomplete":
                reason = "incomplete_evidence"
            else:
                reason = "unsupported"
            return _result("unknown", reason, attempts, started, observed_at, last_observation)
        if state not in _PROCESSING:
            return _result("unknown", "unreadable", attempts, started, observed_at, last_observation)

        if attempts >= policy.max_attempts:
            return _result("unknown", "attempt_limit", attempts, started, observed_at, last_observation)
        remaining = deadline - observed_at
        if remaining <= 0:
            return _result("unknown", "deadline", attempts, started, observed_at, last_observation)
        wait_interval = min(policy.interval_seconds, remaining)
        if wait_interval < 0:
            return _result("unknown", "deadline", attempts, started, observed_at, last_observation)
        try:
            sleep(wait_interval)
        except TimeoutError:
            return _result("unknown", "request_timeout", attempts, started, clock(), last_observation)
        except Exception as exc:
            if exc.__class__.__name__ in {"CancelledError", "CanceledError"}:
                return _result("unknown", "cancelled", attempts, started, clock(), last_observation)
            return _result("unknown", "unreadable", attempts, started, clock(), last_observation)
        except BaseException as exc:
            # asyncio.CancelledError inherits BaseException on supported
            # Python versions; do not swallow unrelated process interrupts.
            if exc.__class__.__name__ in {"CancelledError", "CanceledError"}:
                return _result("unknown", "cancelled", attempts, started, clock(), last_observation)
            raise

    # The loop's attempt-limit return is normally reached inside the loop;
    # keep a defensive result for unusual integer-like policy implementations.
    return _result("unknown", "attempt_limit", attempts, started, clock(), last_observation)


__all__ = ["ReadOnlyCallback", "WaitPolicy", "WaitResult", "wait_for_confirmation"]
