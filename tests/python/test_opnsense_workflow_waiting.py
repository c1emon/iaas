from __future__ import annotations

import asyncio

import pytest

from iaas.opnsense_workflow.waiting import WaitPolicy, wait_for_confirmation


class FakeClock:
    def __init__(self) -> None:
        self.value = 0.0
        self.sleeps: list[float] = []

    def now(self) -> float:
        return self.value

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.value += seconds


def test_delayed_completion_uses_only_read_callback_and_keeps_bounds() -> None:
    clock = FakeClock()
    responses = iter([{"status": "processing", "members": []},
                      {"status": "confirmed", "complete": True, "fresh": True, "members": ["a"]}])
    timeouts: list[float] = []

    def read(timeout: float) -> dict:
        timeouts.append(timeout)
        return next(responses)

    result = wait_for_confirmation(read, clock=clock.now, sleep=clock.sleep)

    assert result.status == "confirmed"
    assert result.reason == "completed"
    assert result.attempts == 2
    assert result.last_observation == {"status": "confirmed", "complete": True, "fresh": True, "members": ["a"]}
    assert timeouts == [15.0, 15.0]
    assert clock.sleeps == [2.0]


def test_explicit_failure_is_terminal_and_is_not_retried() -> None:
    clock = FakeClock()
    calls = 0

    def read(timeout: float) -> dict:
        nonlocal calls
        calls += 1
        return {"status": "failed", "reason": "provider rejected"}

    result = wait_for_confirmation(read, clock=clock.now, sleep=clock.sleep)

    assert result.status == "failed"
    assert result.reason == "explicit_failure"
    assert result.attempts == calls == 1
    assert clock.sleeps == []


def test_request_timeout_and_interval_are_clamped_to_remaining_deadline() -> None:
    clock = FakeClock()
    timeouts: list[float] = []

    def read(timeout: float) -> dict:
        timeouts.append(timeout)
        return {"status": "processing", "attempt": len(timeouts)}

    result = wait_for_confirmation(
        read,
        policy=WaitPolicy(deadline_seconds=5, max_attempts=10, request_timeout_seconds=10, interval_seconds=4),
        clock=clock.now,
        sleep=clock.sleep,
    )

    assert result.status == "unknown"
    assert result.reason == "deadline"
    assert result.attempts == 2
    assert result.last_observation == {"status": "processing", "attempt": 2}
    assert timeouts == [5.0, 1.0]
    assert clock.sleeps == [4.0, 1.0]


def test_attempt_limit_preserves_last_processing_observation() -> None:
    clock = FakeClock()

    result = wait_for_confirmation(
        lambda timeout: {"status": "processing", "timeout": timeout},
        policy=WaitPolicy(deadline_seconds=100, max_attempts=3, request_timeout_seconds=7, interval_seconds=2),
        clock=clock.now,
        sleep=clock.sleep,
    )

    assert result.status == "unknown"
    assert result.reason == "attempt_limit"
    assert result.attempts == 3
    assert result.last_observation == {"status": "processing", "timeout": 7}
    assert clock.sleeps == [2.0, 2.0]


def test_zero_interval_continues_until_attempt_limit() -> None:
    clock = FakeClock()
    calls = 0

    def read(timeout: float) -> dict:
        nonlocal calls
        calls += 1
        return {"status": "processing", "attempt": calls}

    result = wait_for_confirmation(
        read,
        policy=WaitPolicy(deadline_seconds=5, max_attempts=3, request_timeout_seconds=1, interval_seconds=0),
        clock=clock.now,
        sleep=clock.sleep,
    )

    assert result.status == "unknown"
    assert result.reason == "attempt_limit"
    assert result.attempts == calls == 3
    assert clock.sleeps == [0.0, 0.0]


@pytest.mark.parametrize("status", ["accepted", "pending", "unconfirmed", "unknown", "incomplete"])
def test_non_processing_states_are_unknown_without_polling_again(status: str) -> None:
    clock = FakeClock()
    calls = 0

    def read(timeout: float) -> dict:
        nonlocal calls
        calls += 1
        return {"status": status}

    result = wait_for_confirmation(read, clock=clock.now, sleep=clock.sleep)

    assert result.status == "unknown"
    assert result.attempts == calls == 1
    assert clock.sleeps == []


@pytest.mark.parametrize(
    "evidence",
    [{}, {"complete": False, "fresh": True}, {"complete": True, "fresh": False},
     {"complete": True, "fresh": True, "truncated": True}],
)
def test_confirmed_requires_complete_fresh_evidence(evidence: dict) -> None:
    clock = FakeClock()
    observation = {"status": "confirmed", **evidence}

    result = wait_for_confirmation(lambda timeout: observation, clock=clock.now, sleep=clock.sleep)

    assert result.status == "unknown"
    assert result.reason == "incomplete_evidence"
    assert result.attempts == 1
    assert result.last_observation == observation
    assert clock.sleeps == []


def test_sleep_cancellation_is_unknown_and_retains_last_observation() -> None:
    clock = FakeClock()

    def cancel_sleep(seconds: float) -> None:
        raise asyncio.CancelledError()

    result = wait_for_confirmation(
        lambda timeout: {"status": "processing", "seen": True},
        clock=clock.now,
        sleep=cancel_sleep,
    )

    assert result.status == "unknown"
    assert result.reason == "cancelled"
    assert result.attempts == 1
    assert result.last_observation == {"status": "processing", "seen": True}


@pytest.mark.parametrize(
    ("failure", "reason"),
    [(TimeoutError(), "request_timeout"), (asyncio.CancelledError(), "cancelled")],
)
def test_cancel_or_request_timeout_is_unknown_and_retains_last_observation(failure: BaseException, reason: str) -> None:
    clock = FakeClock()
    calls = 0

    def read(timeout: float) -> dict:
        nonlocal calls
        calls += 1
        if calls == 1:
            return {"status": "processing", "observed": calls}
        raise failure

    result = wait_for_confirmation(read, clock=clock.now, sleep=clock.sleep)

    assert result.status == "unknown"
    assert result.reason == reason
    assert result.attempts == 2
    assert result.last_observation == {"status": "processing", "observed": 1}
    assert clock.sleeps == [2.0]


def test_mapping_timeout_or_cancel_status_is_unknown_without_another_read() -> None:
    clock = FakeClock()
    responses = iter([{"status": "timeout", "detail": "read deadline"}])
    calls = 0

    def read(timeout: float) -> dict:
        nonlocal calls
        calls += 1
        return next(responses)

    result = wait_for_confirmation(read, clock=clock.now, sleep=clock.sleep)

    assert result.status == "unknown"
    assert result.reason == "request_timeout"
    assert result.attempts == calls == 1
    assert result.last_observation == {"status": "timeout", "detail": "read deadline"}
    assert clock.sleeps == []


@pytest.mark.parametrize(
    "field,value",
    [("deadline_seconds", 0), ("max_attempts", 0), ("request_timeout_seconds", 0), ("interval_seconds", -1)],
)
def test_wait_policy_rejects_invalid_limits(field: str, value: int) -> None:
    with pytest.raises(ValueError):
        WaitPolicy(**{field: value})
