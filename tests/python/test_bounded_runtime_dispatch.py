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
    assert report['credential_names'] == []
    spec['options'] = {}
    entry.write_text(yaml.safe_dump({'schema_version': 1, 'environment': 'test', 'components': {component: spec}}))
    with pytest.raises(ValidationError, match='explicit execution_mode'):
        load_operation(entry, component, operation, None, SourceReader())


def test_capabilities_declare_bounded_mode_effects():
    for component, operation in [('pve-template', 'accept'), ('pve', 'snippet-cleanup')]:
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
        component: {'inputs': {}, 'files': {alias: str(request), 'original_execution_dir': str(original)},
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
    from test_pve_template_acceptance import API, DIGEST, admission, request
    from iaas.pve_template import acceptance

    value = request()
    req = tmp_path / 'request.json'
    req.write_text(json.dumps(value))
    adm = tmp_path / 'admission.json'
    adm.write_text(json.dumps(admission(value)))
    entry = tmp_path / 'entry.yml'
    entry.write_text(yaml.safe_dump({'schema_version': 1, 'environment': 'test', 'components': {
        'pve-template': {'inputs': {}, 'files': {'acceptance_request': str(req), 'execution_admission': str(adm)},
                         'options': {'execution_mode': 'start'}}}}))
    api = API(value)
    monkeypatch.setattr(acceptance.pve, '_client', lambda *args: api)
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
