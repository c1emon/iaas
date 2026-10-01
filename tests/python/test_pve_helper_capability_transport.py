"""Capability transport uses bounded readonly wrapper calls before mutation."""
import json
import time
from types import SimpleNamespace

import pytest

from iaas.pve_template import acceptance_snippets as mod
from iaas.pve_template.admission import AdmissionError


@pytest.mark.parametrize('complete', [True, False])
def test_capability_transport_rejects_missing_support(monkeypatch, complete):
    helper = mod.Snippets.__new__(mod.Snippets)
    helper.command, helper.env = ['ssh', 'fixture'], {}
    helper.deadline, helper.budget = time.monotonic() + 10, None
    declaration = {'schema_version': 'helper-capabilities/v1', 'helper': 'upload',
                   'protocol_version': 2, 'capabilities': {'acceptance': True, 'create_only': complete,
                   'verify': True, 'deadline': True}}
    calls = []

    def run(args, **kwargs):
        calls.append(args)
        assert kwargs['timeout'] <= 10
        return SimpleNamespace(stdout=json.dumps(declaration))

    monkeypatch.setattr(mod.subprocess, 'run', run)
    if complete:
        assert helper.capabilities('upload') == declaration
    else:
        with pytest.raises(AdmissionError, match='helper_capability_missing'):
            helper.capabilities('upload')
    assert len(calls) == 1
    assert calls[0][-1] == 'sudo -n /usr/local/sbin/iaas-pve-snippet-upload --capabilities'


def test_file_inspection_uses_same_isolated_readonly_transport(monkeypatch):
    helper = mod.Snippets.__new__(mod.Snippets)
    helper.command, helper.env = ['ssh', 'fixture'], {}
    helper.deadline = time.monotonic() + 10
    helper.phase = 'cleanup'
    helper.budget = SimpleNamespace(deadlines={'cleanup_deadline_at': '2099-01-01T00:00:00Z'},
                                    remaining=lambda phase: 10)
    expected = {'schema_version': 2, 'existence': 'present', 'sha256': 'a' * 64, 'digest_matches': True}
    calls = []
    def run(args, **kwargs):
        calls.append(args)
        return SimpleNamespace(stdout=json.dumps(expected))
    monkeypatch.setattr(mod.subprocess, 'run', run)
    snippet = {'storage': 'local', 'file_name': 'accept-9100-user-data.yml', 'sha256': 'a' * 64}
    assert helper.inspect_file(snippet) == expected
    assert calls[0][-1] == ('sudo -n /usr/local/sbin/iaas-pve-snippet-delete --inspect-file '
        '--storage local --filename accept-9100-user-data.yml --sha256 ' + 'a' * 64 +
        ' --deadline-at 2099-01-01T00:00:00Z')
