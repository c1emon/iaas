from iaas.observation import Decision, EvidenceSink, ObservationBudget, observe, task_decision
from iaas.pve_template.responses import RequestOutcomeUnknown, read_retry_decision


class Clock:
    def __init__(self):
        self.utc = 1000.0
        self.mono = 10.0

    def sleep(self, seconds):
        self.utc += seconds
        self.mono += seconds


def test_fixed_task_retry_and_frozen_failed_evidence():
    clock = Clock()
    budget = ObservationBudget(5, utc=lambda: clock.utc, monotonic=lambda: clock.mono)
    sink = EvidenceSink()
    calls = []
    values = iter([RequestOutcomeUnknown(503), {'status': 'running'},
                   {'status': 'stopped', 'exitstatus': 'unexpected status'}])
    def probe(timeout):
        calls.append(('original-upid', timeout))
        value = next(values)
        if isinstance(value, Exception):
            raise value
        return value
    result = observe(probe, task_decision, budget, 'work', 'task', {'upid': 'original-upid'},
                     sink, retry_error=read_retry_decision, sleep=clock.sleep, utc=lambda: clock.utc)
    assert result.status == 'failed'
    assert calls == [('original-upid', 5), ('original-upid', 4), ('original-upid', 3)]
    observe(lambda _: {}, lambda _: Decision('ready', 'source_unchanged'), budget,
            'work', 'source', {'vmid': 9000}, sink)
    assert sink.rows()[0]['terminal']['evidence']['exitstatus'] == 'unexpected status'
    assert len(sink.rows()) == 2


def test_expiry_no_new_probe_preserves_last_and_missing_terminal_is_unknown():
    clock = Clock()
    budget = ObservationBudget(2, utc=lambda: clock.utc, monotonic=lambda: clock.mono)
    sink = EvidenceSink()
    calls = []
    def probe(timeout):
        calls.append(timeout)
        if len(calls) == 2:
            raise RequestOutcomeUnknown(503)
        return {'status': 'stopped'}
    result = observe(probe, task_decision, budget, 'work', 'task', {'upid': 'same'}, sink,
                     sleep=clock.sleep, utc=lambda: clock.utc, retry_error=read_retry_decision)
    assert result.status == 'unknown'
    assert calls == [2, 1]
    assert sink.rows()[0]['last_observation']['observed_at'] == '1970-01-01T00:16:40Z'
    assert sink.rows()[0]['last_observation']['evidence'] == {'status': 'stopped'}


def test_local_limit_and_clock_jumps_never_extend_window():
    clock = Clock()
    budget = ObservationBudget(10, utc=lambda: clock.utc, monotonic=lambda: clock.mono)
    budget.limit('work', 8)
    clock.sleep(2)
    budget.limit('work', 20)
    clock.utc -= 100
    assert budget.remaining('work') == 6
    clock.utc += 105
    assert budget.remaining('work') == 3


def test_unclassified_tls_permission_and_malformed_do_not_retry():
    for error in [RequestOutcomeUnknown(), RequestOutcomeUnknown(403),
                  RequestOutcomeUnknown(category='tls'), RequestOutcomeUnknown(category='invalid_response')]:
        calls = []
        def probe(timeout):
            calls.append(timeout)
            raise error
        result = observe(probe, task_decision, ObservationBudget(5), 'work', 'task', {'upid': 'same'},
                         retry_error=read_retry_decision)
        assert result.status == 'unknown'
        assert len(calls) == 1


def test_safe_group_evidence_preserves_two_volume_failure_without_payload():
    sink = EvidenceSink()
    result = observe(lambda _: None,
                     lambda _: Decision('failed', 'owner_conflict', {
                         'actual': [{'volid': 's:vm-1-a', 'vmid': 1}, {'volid': 's:vm-1-b', 'vmid': 2}],
                         'token': 'private', 'raw_response': {'secret': 'private'}}),
                     ObservationBudget(), 'work', 'claim', {'vmid': 1}, sink)
    assert result.evidence == {'actual': [{'volid': 's:vm-1-a', 'vmid': 1}, {'volid': 's:vm-1-b', 'vmid': 2}]}
    assert sink.rows()[0]['terminal']['reason'] == 'owner_conflict'
