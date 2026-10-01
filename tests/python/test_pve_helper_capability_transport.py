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
