"""Frozen native operation budgets; observation never constructs one."""
from __future__ import annotations

import time
import math

from iaas.pve_acceptance_contracts import deadline_timestamp
from iaas.runtime_execution.execution import OperationFailed


class DeadlineExpired(OperationFailed):
    def __init__(self, phase: str) -> None:
        self.phase = phase
        super().__init__(f'{phase}_deadline_expired')


class LocalTimeout(OperationFailed):
    def __init__(self, phase: str) -> None:
        self.phase = phase
        super().__init__(f'{phase}_timeout')


class DeadlineBudget:
    def __init__(self, deadlines: dict[str, str]) -> None:
        self.deadlines = dict(deadlines)
        utc, monotonic = time.time(), time.monotonic()
        if not math.isfinite(utc) or not math.isfinite(monotonic):
            raise OperationFailed('execution clock unavailable')
        self.absolute = {phase: deadline_timestamp(deadlines[f'{phase}_deadline_at'])
                         for phase in ('work', 'cleanup')}
        self.bounds = {phase: monotonic + cutoff - utc for phase, cutoff in self.absolute.items()}
        self.local = {phase: float('inf') for phase in self.absolute}
        self.outcome: dict = {'phase': None, 'status': 'not_exceeded'}

    def admit(self) -> None:
        try:
            for phase in ('work', 'cleanup'):
                self.remaining(phase)
        except DeadlineExpired:
            self.outcome = {'phase': 'admission', 'status': 'rejected'}
            raise

    def remaining(self, phase: str) -> float:
        utc, now = time.time(), time.monotonic()
        if not math.isfinite(utc) or not math.isfinite(now):
            raise OperationFailed('execution clock unavailable')
        # UTC forward jumps permanently tighten the start-frozen bound.
        self.bounds[phase] = min(self.bounds[phase], now + self.absolute[phase] - utc)
        remaining = self.bounds[phase] - now
        if remaining <= 0:
            self.outcome = {'phase': phase, 'status': 'exceeded'}
            raise DeadlineExpired(phase)
        local_remaining = self.local[phase] - now
        if local_remaining <= 0:
            raise LocalTimeout(phase)
        return min(remaining, local_remaining)

    def limit(self, phase: str, seconds: float) -> None:
        self.local[phase] = min(self.local[phase], time.monotonic() + seconds)
