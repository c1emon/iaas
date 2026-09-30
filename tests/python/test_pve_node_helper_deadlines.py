"""Remote helper deadlines: late requests cannot mutate facility files."""
from datetime import datetime, timedelta, timezone
import hashlib
import importlib.machinery
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]
UPLOAD = ROOT / 'automation/pve-node/bin/iaas-pve-snippet-upload'
DELETE = ROOT / 'automation/pve-node/bin/iaas-pve-snippet-delete'


@pytest.fixture
def helper():
    loader = importlib.machinery.SourceFileLoader('deadline_delete_helper', str(DELETE))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


def test_delete_requires_valid_deadline():
    for args in ([], ['--deadline-at', '2099-01-01T00:00:00+00:00'],
                 ['--deadline-at', '2099-02-30T00:00:00Z']):
        result = subprocess.run([str(DELETE), '--inspect-cluster', *args], text=True, capture_output=True)
        assert result.returncode != 0


def test_delete_expired_before_path_resolution(helper, monkeypatch):
    calls = []
    monkeypatch.setattr(helper.subprocess, 'run', lambda *a, **k: calls.append(k))
    assert helper.delete_exact('local', 'vm-100-user-data.yml', 'a' * 64,
                               helper.Deadline('2000-01-01T00:00:00Z')) == ('failed', 'cleanup_deadline_expired')
    assert calls == []


def test_delete_rechecks_after_hash_before_unlink(helper, monkeypatch, tmp_path):
    target = tmp_path / 'snippets/vm-100-user-data.yml'
    target.parent.mkdir()
    target.write_bytes(b'owned')
    clock = {'utc': 100., 'mono': 50.}
    monkeypatch.setattr(helper.time, 'time', lambda: clock['utc'])
    monkeypatch.setattr(helper.time, 'monotonic', lambda: clock['mono'])
    cutoff = helper.Deadline('1970-01-01T00:01:50Z')
    timeouts = []
    def resolve(*args, **kwargs):
        timeouts.append(kwargs['timeout'])
        return SimpleNamespace(stdout=str(target))
    monkeypatch.setattr(helper.subprocess, 'run', resolve)
    original_stat = helper.os.stat
    count = 0
    def stat_then_expire(*args, **kwargs):
        nonlocal count
        result = original_stat(*args, **kwargs)
        count += 1
        if count == 2:
            clock['utc'] = 110.
            clock['mono'] = 60.
        return result
    monkeypatch.setattr(helper.os, 'stat', stat_then_expire)
    digest = hashlib.sha256(b'owned').hexdigest()
    assert helper.delete_exact('local', target.name, digest, cutoff) == ('failed', 'cleanup_deadline_expired')
    assert target.read_bytes() == b'owned'
    assert timeouts == [10.]


def test_remote_monotonic_limit_cannot_expand(helper, monkeypatch):
    clock = {'utc': 100., 'mono': 50.}
    monkeypatch.setattr(helper.time, 'time', lambda: clock['utc'])
    monkeypatch.setattr(helper.time, 'monotonic', lambda: clock['mono'])
    deadline = helper.Deadline('1970-01-01T00:01:50Z')
    clock.update(utc=90., mono=55.)
    assert deadline.remaining() == 5.
    clock.update(utc=108., mono=55.)
    assert deadline.remaining() == 2.
    clock.update(utc=80., mono=56.)
    assert deadline.remaining() == 1.


def test_upload_mode_requires_deadline_and_refuses_late_create(tmp_path):
    target = tmp_path / 'snippets/accept-100-user-data.yml'
    resolver = tmp_path / 'pvesm'
    resolver.write_text(f'#!/bin/sh\nprintf "%s\\n" "{target}"\n')
    resolver.chmod(0o755)
    env = os.environ | {'IAAS_PVE_SNIPPET_UPLOAD_PVESM': str(resolver)}
    args = ['bash', str(UPLOAD), '--mode', 'acceptance', '--create-only',
            '--storage', 'local', '--filename', target.name]
    missing = subprocess.run(args, input='owned', text=True, capture_output=True, env=env)
    expired = subprocess.run(args + ['--deadline-at', '2000-01-01T00:00:00Z'],
                             input='owned', text=True, capture_output=True, env=env)
    assert missing.returncode != 0 and 'deadline-at is required' in missing.stderr
    assert expired.returncode != 0 and 'work_deadline_expired' in expired.stderr
    assert not target.exists()
    assert not target.parent.exists()


def test_upload_acceptance_success_and_delayed_resolver_budget(tmp_path):
    target = tmp_path / 'snippets/accept-100-user-data.yml'
    resolver = tmp_path / 'pvesm'
    resolver.write_text(f'#!/bin/sh\nprintf "%s\\n" "{target}"\n')
    resolver.chmod(0o755)
    env = os.environ | {'IAAS_PVE_SNIPPET_UPLOAD_PVESM': str(resolver)}
    args = ['bash', str(UPLOAD), '--mode', 'acceptance', '--create-only',
            '--storage', 'local', '--filename', target.name, '--deadline-at']
    valid = subprocess.run(args + ['2099-01-01T00:00:00Z'], input='owned', text=True, capture_output=True, env=env)
    assert valid.returncode == 0, valid.stderr
    assert target.read_bytes() == b'owned'
    target.unlink()
    resolver.write_text(f'#!/bin/sh\nsleep 3\nprintf "%s\\n" "{target}"\n')
    value = (datetime.now(timezone.utc) + timedelta(seconds=2)).strftime('%Y-%m-%dT%H:%M:%SZ')
    late = subprocess.run(args + [value], input='owned', text=True, capture_output=True, env=env)
    assert late.returncode != 0 and 'work_deadline_expired' in late.stderr
    assert not target.exists()


def test_delete_rechecks_deadline_after_lock(helper, monkeypatch, tmp_path, capsys):
    clock = {'utc': 100., 'mono': 50.}
    monkeypatch.setattr(helper.time, 'time', lambda: clock['utc'])
    monkeypatch.setattr(helper.time, 'monotonic', lambda: clock['mono'])
    monkeypatch.setattr(sys, 'argv',
                        [str(DELETE), '--deadline-at', '1970-01-01T00:01:50Z',
                         '--storage', 'local', '--filename', 'vm-100-user-data.yml',
                         '--sha256', 'a' * 64, '--node', 'pve1', '--vmid', '100'])
    original_open = helper.os.open
    monkeypatch.setattr(helper.os, 'open', lambda *a, **k: original_open(tmp_path / 'helper.lock', os.O_RDWR | os.O_CREAT, 0o600))
    monkeypatch.setattr(helper.os, 'fstat', lambda fd: SimpleNamespace(st_uid=0, st_mode=0o100600))
    monkeypatch.setattr(helper.fcntl, 'flock', lambda *a: clock.update(utc=110., mono=60.))
    calls = []
    monkeypatch.setattr(helper, 'inspect_cluster', lambda **k: calls.append(k))
    helper.main()
    result = json.loads(capsys.readouterr().out)
    assert result == {'schema_version': 2, 'status': 'failed', 'reason_code': 'cleanup_deadline_expired'}
    assert calls == []
