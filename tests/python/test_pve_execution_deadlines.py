"""Deadline boundary evidence from controllable clocks and fake facility calls."""
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from iaas.pve_template import deadlines as clock_module
from iaas.pve_template.deadlines import DeadlineBudget
from iaas.pve_template.acceptance_execution import observe, save
from iaas.pve_acceptance_contracts import validate_acceptance_request
from test_pve_template_acceptance import API, DIGEST, Snippets, admission, begin, request, mod


def utc(seconds):
    return datetime.fromtimestamp(seconds, timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


@pytest.fixture
def clock(monkeypatch):
    value = SimpleNamespace(utc=1900000000.0, mono=100.0)
    monkeypatch.setattr(clock_module.time, 'time', lambda: value.utc)
    monkeypatch.setattr(clock_module.time, 'monotonic', lambda: value.mono)
    return value


def bounded(clock, work=10, cleanup=20):
    value = request()
    value['deadlines'] = {'work_deadline_at': utc(clock.utc + work),
                          'cleanup_deadline_at': utc(clock.utc + cleanup)}
    return value


@pytest.mark.parametrize('work', [-1, 0])
def test_admission_expired_is_known_zero_write(clock, tmp_path, work):
    value = bounded(clock, work)
    api = API(value)
    root = tmp_path / 'execution'
    journal = begin(root, 'accept', value, admission(value), 'accept-001', DIGEST)
    result = mod.Acceptance(api, value, journal, root, Snippets(api)).execute()
    assert result['deadline_outcome'] == {'phase': 'admission', 'status': 'rejected'}
    assert result['facility_writes'] == 'none'
    assert result['overall'] != 'passed' and not api.calls


def test_both_monotonic_bounds_frozen_before_clock_rollback(clock):
    value = bounded(clock)
    budget = DeadlineBudget(value['deadlines'])
    assert budget.bounds == {'work': 110, 'cleanup': 120}
    clock.mono += 7
    clock.utc -= 100
    budget.limit('cleanup', 100)
    assert budget.remaining('cleanup') == 13
    clock.utc += 119
    assert budget.remaining('cleanup') == 1
    clock.utc -= 100
    assert budget.remaining('cleanup') == 1


def test_stage_delay_enters_cleanup_without_starting_vm(clock, tmp_path):
    value = bounded(clock)
    api = API(value)
    original = api.request
    def call(method, path, **kwargs):
        answer = original(method, path, **kwargs)
        if path.endswith('/config') and method == 'PUT':
            clock.utc += 10
            clock.mono += 10
        return answer
    api.request = call
    root = tmp_path / 'execution'
    journal = begin(root, 'accept', value, admission(value), 'accept-001', DIGEST)
    result = mod.Acceptance(api, value, journal, root, Snippets(api)).execute()
    assert not any(path.endswith('/status/start') for _, path, _, _ in api.calls)
    assert result['cleanup']['vm']['status'] == 'passed'
    assert result['overall'] != 'passed'
    assert result['deadline_outcome'] == {'phase': 'work', 'status': 'exceeded'}


def test_intent_persistence_expiry_does_not_send_clone(clock, tmp_path, monkeypatch):
    value = bounded(clock)
    api = API(value)
    root = tmp_path / 'execution'
    journal = begin(root, 'accept', value, admission(value), 'accept-001', DIGEST)
    worker = mod.Acceptance(api, value, journal, root, Snippets(api))
    persist = worker.persist
    def delayed():
        persist()
        if journal['tasks'] and journal['tasks'][-1]['status'] == 'intent':
            clock.utc += 10
            clock.mono += 10
    monkeypatch.setattr(worker, 'persist', delayed)
    result = worker.execute()
    assert not any(method != 'GET' for method, _, _, _ in api.calls)
    assert result['facility_writes'] == 'none'
    assert journal['tasks'][0]['status'] == 'not_sent'
    assert result['temporary_resources'] == [] and result['residuals']['items'] == []


def test_api_timeout_cannot_exceed_remaining_work(clock, tmp_path):
    value = bounded(clock, work=3)
    api = API(value)
    original = api.request
    observed = []
    def call(method, path, **kwargs):
        observed.append(api.timeout)
        return original(method, path, **kwargs)
    api.request = call
    root = tmp_path / 'execution'
    journal = begin(root, 'accept', value, admission(value), 'accept-001', DIGEST)
    worker = mod.Acceptance(api, value, journal, root, Snippets(api))
    worker.api('GET', worker.source + '/config')
    clock.utc += 2
    clock.mono += 2
    worker.api('GET', worker.source + '/config')
    assert observed == [3, 1]


def test_guest_exec_response_loss_blocks_destructive_cleanup(tmp_path):
    value = request()
    api = API(value)
    original = api.request
    def call(method, path, **kwargs):
        if path.endswith('/agent/exec'):
            raise TimeoutError('response lost')
        return original(method, path, **kwargs)
    api.request = call
    root = tmp_path / 'execution'
    journal = begin(root, 'accept', value, admission(value), 'accept-001', DIGEST)
    result = mod.Acceptance(api, value, journal, root, Snippets(api)).execute()
    assert result['overall'] == 'unknown' and journal['mutation_active'] is True
    assert journal['tasks'][-1]['phase'] == 'guest_exec'
    assert not any(method == 'DELETE' for method, _, _, _ in api.calls)


def test_sent_task_expiry_retains_unknown_activity(clock, tmp_path):
    value = bounded(clock)
    api = API(value)
    original = api.request
    def call(method, path, **kwargs):
        answer = original(method, path, **kwargs)
        if path.endswith('/clone'):
            clock.utc += 10
            clock.mono += 10
        return answer
    api.request = call
    root = tmp_path / 'execution'
    journal = begin(root, 'accept', value, admission(value), 'accept-001', DIGEST)
    result = mod.Acceptance(api, value, journal, root, Snippets(api)).execute()
    assert result['overall'] == 'unknown' and journal['mutation_active'] is True
    assert not any(method == 'DELETE' for method, _, _, _ in api.calls)
    assert journal['tasks'][0]['upid']


@pytest.mark.parametrize('stamp', ['2026-02-30T12:00:00Z', '2026-01-01T12:00:00+00:00',
                                  '2026-01-01T12:00:00.1Z', '2026-01-01T12:00:60Z'])
def test_invalid_deadline_formats_rejected(stamp):
    value = request()
    value['deadlines']['work_deadline_at'] = stamp
    with pytest.raises(ValueError):
        validate_acceptance_request(value)


def test_observe_expiry_does_not_construct_budget(clock, tmp_path, monkeypatch):
    value = bounded(clock)
    root = tmp_path / 'execution'
    journal = begin(root, 'accept', value, admission(value), 'accept-001', DIGEST)
    clock.utc += 100
    monkeypatch.setattr(DeadlineBudget, '__init__', lambda *args: pytest.fail('observe restarted budget'))
    before = (root / 'journal.json').read_bytes()
    assert observe(root, 'accept', value, 'accept-001') == (journal, None)
    assert (root / 'journal.json').read_bytes() == before


def test_admission_and_observation_deadline_conflicts_rejected(tmp_path):
    value = request()
    authorization = admission(value)
    authorization['deadlines'] = {**value['deadlines'], 'cleanup_deadline_at': '2100-01-01T00:00:00Z'}
    with pytest.raises(ValueError):
        begin(tmp_path / 'bad', 'accept', value, authorization, 'accept-001', DIGEST)
    root = tmp_path / 'execution'
    journal = begin(root, 'accept', value, admission(value), 'accept-001', DIGEST)
    journal['deadlines'] = authorization['deadlines']
    save(root / 'journal.json', journal)
    with pytest.raises(ValueError):
        observe(root, 'accept', value, 'accept-001')
