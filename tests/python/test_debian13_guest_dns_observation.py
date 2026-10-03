"""Exercise the guest program with direct/stub resolver runtime material."""
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from iaas.pve_template.guest_observation import GENERAL_GUEST_OBSERVATION


@pytest.mark.parametrize('resolver,upstream,expected,valid', [
    ('nameserver 10.5.0.15\n', None, ['10.5.0.15'], True),
    ('nameserver 127.0.0.53\n', '# runtime uplink\n nameserver 10.5.0.15\n', ['10.5.0.15'], True),
    ('nameserver 127.0.0.53\n', None, ['127.0.0.53'], False),
    ('nameserver 127.0.0.53\n', 'nameserver 192.0.2.53\n', ['192.0.2.53'], False),
])
def test_guest_observes_actual_dns_without_inventing_expected_values(monkeypatch, capsys, resolver, upstream, expected, valid):
    import os
    import subprocess

    responses = {
        ('cloud-init', 'status', '--format', 'json'): '{"status":"done"}',
        ('findmnt', '-n', '-o', 'SOURCE', '/'): '/dev/sda1',
        ('lsblk', '--nodeps', '-n', '-o', 'PKNAME', '/dev/sda1'): 'sda',
        ('ip', '-j', 'address'): '[]',
        ('ip', '-j', 'route'): '[]',
        ('blockdev', '--getsize64', '/dev/sda1'): str(127 * 1024**3),
        ('blockdev', '--getsize64', '/dev/sda'): str(128 * 1024**3),
        ('cloud-init', 'query', 'instance_id'): 'iaas-acceptance-synthetic',
    }
    files = {'/etc/resolv.conf': resolver, '/etc/machine-id': 'a' * 32}
    if upstream is not None:
        files['/run/systemd/resolve/resolv.conf'] = upstream
    with monkeypatch.context() as patch:
        patch.setattr(subprocess, 'check_output', lambda command, **kwargs: responses[tuple(command)])
        patch.setattr(os, 'statvfs', lambda path: SimpleNamespace(f_blocks=127 * 1024**2, f_frsize=1024))
        patch.setattr(Path, 'read_text', lambda path, **kwargs: files[str(path)])
        patch.setattr(Path, 'is_file', lambda path: str(path) in files)
        exec(GENERAL_GUEST_OBSERVATION, {})
    facts = json.loads(capsys.readouterr().out)['general_template']
    assert facts['nameservers'] == expected
    assert ('10.5.0.15' in facts['nameservers']) is valid
    assert facts['resolver_nameservers'] == [resolver.split()[1]]
