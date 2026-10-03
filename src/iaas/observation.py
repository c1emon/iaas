"""Finite read-only observation. Dispatch belongs to the calling domain."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import math
import re
import time
from typing import Any, Callable


@dataclass(frozen=True)
class Decision:
    status: str
    reason: str
    evidence: dict[str, Any] = field(default_factory=dict)


class ObservationExpired(Exception):
    pass


def utc_text(value: float) -> str:
    return datetime.fromtimestamp(value, timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


class ObservationBudget:
    """One read-only/task window, never renewed by a probe or substage."""
    def __init__(self, seconds: float = 120, *, cutoff: float | None = None,
                 source: str = 'internal-default', utc=time.time, monotonic=time.monotonic):
        if not math.isfinite(seconds) or seconds <= 0:
            raise ValueError('observation timeout must be finite and positive')
        self.utc, self.monotonic = utc, monotonic
        self.started_at, now = utc(), monotonic()
        self.cutoff = min(self.started_at + seconds, cutoff) if cutoff is not None else self.started_at + seconds
        self.bound = now + self.cutoff - self.started_at
        self.source = source
        self.local = float('inf')

    def remaining(self, phase: str = 'work') -> float:
        utc, now = self.utc(), self.monotonic()
        if not math.isfinite(utc) or not math.isfinite(now):
            raise ObservationExpired('clock_unavailable')
        self.bound = min(self.bound, now + self.cutoff - utc)
        remaining = min(self.bound, self.local) - now
        if remaining <= 0:
            raise ObservationExpired('observation_deadline_expired')
        return remaining

    def limit(self, phase: str, seconds: float) -> None:
        self.local = min(self.local, self.monotonic() + seconds)

    def facts(self) -> dict:
        return {'source': self.source, 'started_at': utc_text(self.started_at), 'cutoff': utc_text(self.cutoff)}


# Domain adapters pass only decision facts. Arbitrary payload/exception text is
# never copied, even when nested under expected/actual.
_FIELDS = frozenset({'vmid', 'volid', 'size', 'size_bytes', 'capacity', 'uuid', 'smbios_uuid',
                     'upid', 'pid', 'node', 'storage', 'pool', 'slot', 'slots', 'volumes',
                     'status', 'exitstatus', 'exists', 'complete', 'registered', 'activity',
                     'expected', 'actual', 'reason', 'category', 'http_status', 'template',
                     'digest', 'inode', 'matched', 'missing', 'config_matches', 'owner',
                     'running', 'exited', 'exitcode', 'ready', 'present', 'absent',
                     'root_disk_bytes', 'root_partition_bytes', 'root_filesystem_bytes',
                     'machine_id_initialized', 'instance_id', 'addresses', 'default_gateways',
                     'nameservers', 'clone_marker', 'ownership', 'existence', 'inventory_complete',
                     'cores', 'memory', 'power', 'checks'})


def safe_facts(value: dict) -> dict:
    def clean(item, depth=0):
        if depth > 6:
            return None
        if isinstance(item, dict):
            return {key: clean(val, depth + 1) for key, val in item.items()
                    if key in _FIELDS or re.fullmatch(r'(?:scsi|virtio|sata|ide|efidisk|tpmstate)\d+', key)}
        if isinstance(item, (list, tuple)):
            return [clean(val, depth + 1) for val in item[:64]]
        if item is None or isinstance(item, (bool, int, float)):
            return item
        if isinstance(item, str):
            return item[:512] if '://' not in item and '\n' not in item else '[excluded]'
        return None
    return clean(value)


class EvidenceSink:
    """Last useful sample and frozen terminal decision per fixed check."""
    def __init__(self):
        self.groups: dict[str, dict] = {}

    def __call__(self, row: dict) -> None:
        import json
        key = json.dumps([row['phase'], row['check'], row['association']], sort_keys=True)
        group = self.groups.setdefault(key, {'phase': row['phase'], 'check': row['check'],
                                             'association': row['association']})
        if 'terminal' in group:
            return
        group['last'] = row
        if (row.get('evidence') and 'category' not in row['evidence']
                and row['reason'] != 'observation_deadline_expired'):
            group['last_observation'] = row
        if row['status'] != 'pending':
            group['terminal'] = row

    def rows(self) -> list[dict]:
        return list(self.groups.values())


def observe(probe: Callable[[float], Any], classify: Callable[[Any], Decision], budget: Any,
            phase: str, check: str, association: dict, sink=None, *, interval: float = 1,
            retry_error: Callable[[Exception], Decision] | None = None, sleep=time.sleep,
            utc=time.time) -> Decision:
    """Only a domain-admitted read probe is accepted; no dispatch callback."""
    attempt = 0
    last: dict = {}
    while True:
        try:
            remaining = budget.remaining(phase)
        except Exception:
            # Budget failures terminate without another online call.
            decision = Decision('unknown', 'observation_deadline_expired', last)
            if sink:
                sink({'phase': phase, 'check': check, 'association': safe_facts(association),
                      'attempt': attempt, 'observed_at': utc_text(utc()), 'status': decision.status,
                      'reason': decision.reason, 'evidence': last})
            return decision
        attempt += 1
        observed_at = utc_text(utc())
        try:
            value = probe(remaining)
        except Exception as exc:
            decision = retry_error(exc) if retry_error else Decision('unknown', 'unclassified_query_error',
                                                                     {'category': 'unclassified'})
        else:
            decision = classify(value)
        if decision.status not in {'ready', 'pending', 'failed', 'unknown'}:
            raise ValueError('invalid observation decision')
        facts = safe_facts(decision.evidence)
        if facts and 'category' not in facts:
            last = facts
        if sink:
            row = {'phase': phase, 'check': check, 'association': safe_facts(association),
                   'attempt': attempt, 'observed_at': observed_at, 'status': decision.status,
                   'reason': decision.reason, 'evidence': facts}
            deadlines = getattr(budget, 'deadlines', None)
            if deadlines:
                row['cutoff'] = deadlines.get(f'{phase}_deadline_at')
            elif hasattr(budget, 'cutoff'):
                row['cutoff'] = utc_text(budget.cutoff)
            sink(row)
        if decision.status != 'pending':
            return Decision(decision.status, decision.reason, facts)
        try:
            sleep(min(interval, budget.remaining(phase)))
        except Exception:
            # Re-enter once to freeze terminal evidence without issuing a probe.
            continue


def task_decision(row: Any) -> Decision:
    if not isinstance(row, dict) or row.get('status') not in {'running', 'stopped'}:
        return Decision('unknown', 'invalid_task_response')
    facts = {key: row[key] for key in ('status', 'exitstatus') if key in row}
    if row['status'] == 'running':
        return Decision('pending', 'task_running', facts)
    if not row.get('exitstatus'):
        return Decision('pending', 'task_terminal_outcome_missing', facts)
    if not isinstance(row['exitstatus'], str):
        return Decision('unknown', 'invalid_task_response', facts)
    return Decision('ready' if row['exitstatus'] == 'OK' else 'failed',
                    'task_ok' if row['exitstatus'] == 'OK' else 'task_failed', facts)
