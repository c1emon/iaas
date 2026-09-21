"""Local source identity, credential/output boundaries and shared execution gates."""
from argparse import Namespace
from pathlib import Path

import pytest
import yaml

from iaas_automation.common.errors import ValidationError
from iaas_automation.opnsense_workflow import local


class FakeReader:
    closed = False

    def __init__(self, target, credentials):
        pass

    def read(self, resources):
        return {resource: {'status': 'complete', 'observation_scope': 'configuration',
                           'objects': [], 'interfaces': ['lan', 'wan'],
                           'interfaces_status': 'complete'} for resource in resources}

    def close(self):
        self.closed = True


@pytest.fixture
def local_args(tmp_path, monkeypatch):
    monkeypatch.setattr(local, 'Reader', FakeReader)
    monkeypatch.setattr(local, 'source_identity', lambda root: {'kind': 'local-source', 'source_sha256': 'a' * 64})
    spec = {'target': {'host': 'test', 'endpoint': 'https://test.invalid', 'ssl_verify': True},
            'request': {'schema_version': 1, 'selection': {'aliases': 'all'}},
            'documents': {'aliases': {'opnsense_aliases': [
                {'name': 'TEST_LOCAL', 'type': 'host', 'content': ['192.0.2.1'], 'state': 'present', 'description': 'local test', 'enabled': True}]}}}
    path = tmp_path / 'input.yml'
    path.write_text(yaml.safe_dump(spec))
    return Namespace(operation='plan', input=path, output=tmp_path / 'plan', candidate=None,
                     candidate_sha256=None, execution_id=None, activation_check=None,
                     recovery=None, allow_test_writes=False, check_mode=False)


def test_local_plan_private_outputs_and_no_image_identity(local_args):
    result = local.run_local(local_args)
    assert result['status'] == 'planned'
    candidate = local_args.output / 'plan/candidate.json'
    assert candidate.stat().st_mode & 0o777 == 0o600
    assert local_args.output.stat().st_mode & 0o777 == 0o700
    assert result['runtime']['kind'] == 'local-source'
    assert 'image_digest' not in result['runtime']
    assert result['business_acceptance'] == 'not_performed'


def prepared_apply(args):
    result = local.run_local(args)
    args.candidate = args.output / 'plan/candidate.json'
    args.candidate_sha256 = result['candidate_sha256']
    args.output = args.output.parent / 'apply'
    args.operation = 'apply'
    return args


def test_local_apply_requires_explicit_test_write_flag(local_args):
    args = prepared_apply(local_args)
    with pytest.raises(ValidationError, match='allow-test-writes'):
        local.run_local(args)
    assert not args.output.exists()


def test_local_apply_rejects_source_drift_before_device_access(local_args, monkeypatch):
    args = prepared_apply(local_args)
    monkeypatch.setattr(local, 'source_identity', lambda root: {'kind': 'local-source', 'source_sha256': 'b' * 64})
    monkeypatch.setattr(local, 'Reader', lambda *a: pytest.fail('must reject before connecting'))
    with pytest.raises(ValidationError, match='source or target changed'):
        local.run_local(args)


def test_local_apply_delegates_to_guarded_executor(local_args, monkeypatch):
    args = prepared_apply(local_args)
    args.allow_test_writes = True
    args.execution_id = 'test-execution'
    args.activation_check = args.input.parent / 'activation.json'
    args.activation_check.write_text('{}')
    sentinel = object()
    monkeypatch.setattr(local, 'Writer', lambda *a, **kw: sentinel)
    seen = []

    def guarded_apply(candidate, digest, reader, writer, execution_id, conclusion, output, *, check_mode):
        seen.append((writer, execution_id, conclusion, check_mode))
        raise ValidationError('bound activation check rejected')

    monkeypatch.setattr(local, 'apply', guarded_apply)
    with pytest.raises(ValidationError, match='activation check rejected'):
        local.run_local(args)
    assert seen == [(sentinel, 'test-execution', {}, False)]


def test_source_identity_tracks_dirty_source_not_bytecode(tmp_path):
    for name in ('pyproject.toml', 'uv.lock', 'automation/src/example.py',
                 'automation/ansible/playbook.yml'):
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('original')
    before = local.source_identity(tmp_path)
    cache = tmp_path / 'automation/src/__pycache__'
    cache.mkdir()
    (cache / 'example.pyc').write_bytes(b'cache')
    assert local.source_identity(tmp_path) == before
    (tmp_path / 'automation/src/example.py').write_text('modified')
    assert local.source_identity(tmp_path) != before


def test_local_ansible_uses_uv_interpreter_even_if_parent_overrides_it(local_args, monkeypatch):
    import sys
    captured = []
    original = local.Execution

    def execution(outputs, environ):
        captured.append(environ)
        return original(outputs, environ)

    monkeypatch.setenv('ANSIBLE_PYTHON_INTERPRETER', '/unrelated/system/python')
    monkeypatch.setattr(local, 'Execution', execution)
    local.run_local(local_args)
    assert captured[0]['ANSIBLE_PYTHON_INTERPRETER'] == sys.executable
    assert Path(captured[0]['ANSIBLE_CONFIG']).is_file()
