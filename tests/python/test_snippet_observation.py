from iaas.observation import ObservationBudget, EvidenceSink
from iaas.pve_snippet_cleanup.runtime import observe_file

SNIPPET = {'node': 'pve1', 'storage': 'local', 'file_name': 'exact.yml', 'sha256': 'a' * 64}


class Inspection:
    phase = 'work'
    def __init__(self, views, references=()):
        self.budget = ObservationBudget(.02)
        self.views = iter(views)
        self.references = list(references)
        self.inspections = 0
    def inspect_file(self, snippet):
        self.inspections += 1
        return next(self.views)
    def inspect(self):
        return {'complete': True, 'references': self.references, 'reference_strategy': 'all_storage_aliases_by_filename'}


def test_upload_rechecks_absence_then_matching_digest():
    helper = Inspection([{'existence': 'absent'}, {'existence': 'present', 'digest_matches': True, 'sha256': 'a' * 64}])
    sink = EvidenceSink()
    decision = observe_file(helper, SNIPPET, absent=False, sink=sink, interval=0)
    assert decision.status == 'ready'
    assert helper.inspections == 2
    assert sink.rows()[0]['terminal']['status'] == decision.status


def test_changed_digest_and_foreign_reference_stop_immediately():
    for view, references in [({'existence': 'present', 'digest_matches': False, 'reason_code': 'digest_mismatch'}, ()),
                             ({'existence': 'absent'}, ('exact.yml',))]:
        helper = Inspection([view], references)
        decision = observe_file(helper, SNIPPET, absent=True)
        assert decision.status == 'failed'
        assert helper.inspections == 1


def test_ordinary_verification_retries_only_read_probe(monkeypatch):
    import json
    import subprocess
    from argparse import Namespace
    from iaas.pve_inventory.cloud_init_helpers.model import CloudInitSnippet
    from iaas.pve_inventory.cloud_init_helpers import ssh
    snippet = CloudInitSnippet(vmid=501, name='vm', file_name='vm-501-user-data.yml',
                              file_id='local:snippets/vm-501-user-data.yml', content='hostname: vm\n',
                              byte_count=13, sha256='a' * 64)
    calls = []
    def run(argv, **kwargs):
        calls.append((argv, kwargs['timeout']))
        assert '--verify' in argv[-1] and '--observe' in argv[-1]
        assert kwargs.get('input') is None
        return subprocess.CompletedProcess(argv, 0, stdout=json.dumps({
            'schema_version': 1, 'status': 'pending' if len(calls) == 1 else 'ready',
            'reason_code': 'exact_target_absent' if len(calls) == 1 else 'digest_confirmed',
            'exists': len(calls) > 1}))
    monkeypatch.setattr(ssh.subprocess, 'run', run)
    args = Namespace(storage_id='local', pve_host='pve1', ssh_user='ops', ssh_timeout=1, observation_interval=0)
    ssh.verify_snippets([snippet], args)
    assert len(calls) == 2 and calls[1][1] <= calls[0][1]
    assert args.observations[0]['terminal']['status'] == 'ready'
