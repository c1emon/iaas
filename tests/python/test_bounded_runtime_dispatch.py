"""Bounded operations discover only their selected files and credentials."""
import json

import pytest
import yaml

from iaas.common.errors import ValidationError
from iaas.runtime_config import InputRequired, SourceReader
from iaas.runtime_execution.__main__ import main
from iaas.runtime_execution.operations import capabilities, credential_names, process_environment
from iaas.runtime_execution.selection import load_operation


@pytest.mark.parametrize('component,operation,request_name', [
    ('pve-template', 'accept', 'acceptance_request'),
    ('pve-template', 'recover', 'recovery_request'),
    ('pve', 'snippet-cleanup', 'snippet_cleanup_request'),
])
def test_discovery_explicit_modes_and_readonly_directory_mapping(tmp_path, capsys, component, operation, request_name):
    request = tmp_path / 'request.json'
    request.write_text('{}')
    original = tmp_path / 'original'
    original.mkdir()
    mapped = tmp_path / 'mapped'
    mapped.mkdir()
    entry = tmp_path / 'environment.yml'
    spec = {'inputs': {}, 'files': {request_name: str(request),
            'original_execution_dir': str(original), 'cleanup_evidence_dir': str(original),
            'backend': '/must-not-be-read', 'artifact_locator': '/must-not-be-read'},
            'options': {'execution_mode': 'observe'}}
    entry.write_text(yaml.safe_dump({'schema_version': 1, 'environment': 'test', 'components': {component: spec}}))
    mapping = {str(entry): str(entry), str(request): str(request)}
    with pytest.raises(InputRequired) as error:
        load_operation(entry, component, operation, None, SourceReader(mapping))
    assert error.value.path == original
    mapping[str(original)] = str(mapped)
    selected = load_operation(entry, component, operation, None, SourceReader(mapping))
    assert selected.files['original_execution_dir'] == mapped
    assert 'cleanup_evidence_dir' not in selected.files
    assert 'backend' not in selected.files
    assert 'artifact_locator' not in selected.files
    expected = {'PVE_API_TOKEN', 'PVE_API_CA'}
    if operation == 'snippet-cleanup':
        expected = set()
    assert credential_names(component, operation) == expected
    assert process_environment(component, operation, {'AWS_SECRET_ACCESS_KEY': 'secret',
        'PVE_ARTIFACT_URL': 'secret', 'PVE_API_TOKEN': 'token', 'SSH_AUTH_SOCK': 'socket',
        'PVE_SSH_HOST': 'unbound-host', 'PVE_SSH_USER': 'unbound-user', 'PVE_SSH_PORT': '2222'}) == ({} if operation == 'snippet-cleanup' else {'PVE_API_TOKEN': 'token'})
    assert main(['--environment', str(entry), '--component', component, '--operation', operation,
                 '--execution-id', 'original-1', '--discover']) == 0
    report = json.loads(capsys.readouterr().out)
    assert report['effects']['infrastructure_write'] is False
    assert report['effects']['state'] is False
    assert report['effects']['network'] is False
    assert report['credential_names'] == []
    spec['options'] = {}
    entry.write_text(yaml.safe_dump({'schema_version': 1, 'environment': 'test', 'components': {component: spec}}))
    with pytest.raises(ValidationError, match='explicit execution_mode'):
        load_operation(entry, component, operation, None, SourceReader())


def test_capabilities_declare_bounded_mode_effects():
    for component, operation in [('pve-template', 'accept'), ('pve-template', 'recover'), ('pve', 'snippet-cleanup')]:
        modes = capabilities()['execution_modes'][component][operation]
        assert modes['start']['infrastructure_write'] is True
        assert modes['observe']['infrastructure_write'] is False
        assert not modes['start']['state'] and not modes['observe']['state']


@pytest.mark.parametrize('component,operation,module_name', [
    ('pve-template', 'accept', 'iaas.pve_template.acceptance'),
    ('pve-template', 'read', 'iaas.pve_template.acceptance'),
    ('pve', 'snippet-cleanup', 'iaas.pve_snippet_cleanup.runtime'),
])
def test_bounded_dispatch_to_dedicated_entrypoint(tmp_path, monkeypatch, component, operation, module_name):
    import sys
    from types import ModuleType

    original = tmp_path / 'original'
    original.mkdir()
    request = tmp_path / 'request.json'
    request.write_text('{}')
    alias = 'snippet_cleanup_request' if component == 'pve' else 'acceptance_request'
    entry = tmp_path / 'environment.yml'
    entry.write_text(yaml.safe_dump({'schema_version': 1, 'environment': 'test', 'components': {
        component: {'inputs': {}, 'files': {alias: str(request), 'acceptance_preview': str(request), 'original_execution_dir': str(original)},
                    'options': {'execution_mode': 'observe' if operation == 'read' else 'start'}}}}))
    received = {}
    module = ModuleType(module_name)

    def run(selected, operation, scope, execution, image_digest, execution_id=''):
        received.update(operation=operation, scope=scope, execution_id=execution_id, digest=image_digest)
        execution.finish({'status': 'success'})

    module.run = run
    monkeypatch.setitem(sys.modules, module_name, module)
    args = ['--environment', str(entry), '--component', component, '--operation', operation,
            '--scope', 'lab', '--image-digest', 'sha256:' + 'a' * 64, '--output', str(tmp_path / 'new-output')]
    if operation != 'read':
        args += ['--execution-id', 'original-1']
    assert main(args) == 0
    assert received == {'operation': operation, 'scope': 'lab',
                        'execution_id': '' if operation == 'read' else 'original-1', 'digest': 'sha256:' + 'a' * 64}


def test_actual_acceptance_entrypoint_roundtrip_and_collection_failure(tmp_path, monkeypatch):
    from test_pve_template_acceptance import API, DIGEST, Snippets, admission, request, preview
    from iaas.pve_template import acceptance

    value = request()
    req = tmp_path / 'request.json'
    req.write_text(json.dumps(value))
    planned_value = preview(value)
    adm = tmp_path / 'admission.json'
    adm.write_text(json.dumps(admission(value, planned_value)))
    planned = tmp_path / 'preview.json'
    planned.write_text(json.dumps(planned_value))
    entry = tmp_path / 'entry.yml'
    entry.write_text(yaml.safe_dump({'schema_version': 1, 'environment': 'test', 'components': {
        'pve-template': {'inputs': {}, 'files': {'acceptance_request': str(req), 'acceptance_preview': str(planned), 'execution_admission': str(adm)},
                         'options': {'execution_mode': 'start'}}}}))
    api = API(value)
    monkeypatch.setattr(acceptance.pve, '_client', lambda *args: api)
    monkeypatch.setattr(acceptance.acceptance_snippets, 'Snippets', lambda *args, **kwargs: Snippets())
    args = ['--environment', str(entry), '--component', 'pve-template', '--operation', 'accept',
            '--scope', 'pve1', '--image-digest', DIGEST, '--execution-id', 'accept-001']
    started = tmp_path / 'start'
    assert main(args + ['--output', str(started)]) == 0
    original = started / 'diagnostics/execution'
    entry.write_text(yaml.safe_dump({'schema_version': 1, 'environment': 'test', 'components': {
        'pve-template': {'inputs': {}, 'files': {'original_execution_dir': str(original)},
                         'options': {'execution_mode': 'observe'}}}}))
    monkeypatch.setattr(acceptance.pve, '_client', lambda *args: pytest.fail('observe created client'))
    assert main(args + ['--output', str(tmp_path / 'observed')]) == 0
    real_save = acceptance.save

    def failed_collection(path, document):
        if path.name == 'result.json':
            raise OSError('simulated collection failure')
        real_save(path, document)

    monkeypatch.setattr(acceptance, 'save', failed_collection)
    assert main(args + ['--output', str(tmp_path / 'failed-collection')]) != 0
    assert json.loads((original / 'result.json').read_text())['overall'] == 'passed'


@pytest.mark.parametrize('operation', ['accept', 'read'])
def test_missing_original_material_remains_unknown_in_main_summary(tmp_path, monkeypatch, operation):
    from iaas.pve_template import acceptance

    original = tmp_path / 'incomplete'
    original.mkdir()
    entry = tmp_path / 'entry.yml'
    entry.write_text(yaml.safe_dump({'schema_version': 1, 'environment': 'test', 'components': {
        'pve-template': {'inputs': {}, 'files': {'original_execution_dir': str(original)},
                         'options': {'execution_mode': 'observe'}}}}))
    monkeypatch.setattr(acceptance.pve, '_client', lambda *args: pytest.fail('observe created client'))
    output = tmp_path / 'observation'
    args = ['--environment', str(entry), '--component', 'pve-template', '--operation', operation,
            '--scope', 'pve1', '--output', str(output)]
    if operation == 'accept':
        args += ['--execution-id', 'original-1']
    assert main(args) != 0
    summary = json.loads((output / 'summary.json').read_text())
    assert summary['status'] == 'failed'
    assert summary['overall'] == 'unknown'
    assert summary['reason_code'] == 'original_evidence_unavailable'
    assert summary['phases'] == []


@pytest.mark.parametrize('operation,action,request_alias', [
    ('check', 'accept', 'acceptance_request'),
    ('plan', 'accept', 'acceptance_request'),
    ('plan', 'recover', 'recovery_request'),
])
def test_plan_discovery_preserves_fixed_request_and_excludes_approval(tmp_path, capsys, operation, action, request_alias):
    fixed = b'{"fixed":"unchanged","deadlines":{"work_deadline_at":"2026-10-01T10:00:00Z"}}\n'
    req = tmp_path / 'request.json'
    req.write_bytes(fixed)
    original = tmp_path / 'original'
    original.mkdir()
    cleanup = tmp_path / 'cleanup'
    cleanup.mkdir()
    entry = tmp_path / 'environment.yml'
    entry.write_text(yaml.safe_dump({'schema_version': 1, 'environment': 'test', 'components': {
        'pve-template': {'inputs': {}, 'files': {request_alias: str(req),
            'execution_admission': '/must-not-consume', 'backend': '/must-not-read',
            'original_execution_dir': str(original), 'cleanup_evidence_dir': str(cleanup)},
            'options': {'action': action}}}}))
    selected = load_operation(entry, 'pve-template', operation, None, SourceReader())
    assert selected.files[request_alias].read_bytes() == fixed
    assert 'execution_admission' not in selected.files and 'backend' not in selected.files
    if action == 'recover':
        assert selected.files['original_execution_dir'] == original
        assert selected.files['cleanup_evidence_dir'] == cleanup
    assert main(['--environment', str(entry), '--component', 'pve-template', '--operation', operation,
                 '--discover']) == 0
    report = json.loads(capsys.readouterr().out)
    assert report['action'] == action and report['execution_mode'] is None
    assert not report['effects']['state'] and not report['effects']['infrastructure_write']
    assert report['credential_names'] == ([] if operation == 'check' else ['PVE_API_CA', 'PVE_API_TOKEN'])
    assert req.read_bytes() == fixed


def test_actual_acceptance_check_then_plan_dispatch_is_readonly_and_does_not_consume_approval(tmp_path, monkeypatch):
    from test_pve_template_acceptance import API, DIGEST, Snippets, request
    from iaas.pve_template import runtime, acceptance_snippets

    value = request()
    fixed = tmp_path / 'request.json'
    fixed.write_text(json.dumps(value))
    entry = tmp_path / 'environment.yml'
    entry.write_text(yaml.safe_dump({'schema_version': 1, 'environment': 'fixture', 'components': {
        'pve-template': {'inputs': {}, 'files': {'acceptance_request': str(fixed),
            'execution_admission': '/must-not-consume', 'backend': '/must-not-read'}, 'options': {'action': 'accept'}}}}))
    args = ['--environment', str(entry), '--component', 'pve-template', '--image-digest', DIGEST]
    monkeypatch.setattr(runtime, '_client', lambda *args: pytest.fail('offline check constructed API'))
    monkeypatch.setattr(acceptance_snippets, 'Snippets', lambda *args: pytest.fail('offline check constructed helper'))
    assert main(args + ['--operation', 'check', '--output', str(tmp_path / 'checked')]) == 0
    api = API(value)
    monkeypatch.setattr(runtime, '_client', lambda *args: api)
    monkeypatch.setattr(acceptance_snippets, 'Snippets', lambda *args, **kwargs: Snippets())
    output = tmp_path / 'planned'
    assert main(args + ['--operation', 'plan', '--scope', 'pve1', '--output', str(output)]) == 0
    planned = json.loads((output / 'plan/acceptance-preview.json').read_text())
    assert planned['fixed_input'] == value
    assert planned['facility_writes'] == 'none'
    assert planned['observed']['readiness']['status'] == 'ready'
    assert all(method == 'GET' for method, *_ in api.calls)
    assert fixed.read_text() == json.dumps(value)
