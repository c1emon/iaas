"""Actual shared runtime dispatch with software API/helper fixtures only."""
from pathlib import Path
import json

import pytest
import yaml

from iaas.runtime_execution.__main__ import main
from iaas.pve_template import recovery, runtime, acceptance_snippets
from test_pve_acceptance_recovery import setup, ID


def write_entry(path, files, options):
    path.write_text(yaml.safe_dump({'schema_version': 1, 'environment': 'fixture', 'components': {
        'pve-template': {'inputs': {}, 'files': {name: str(value) for name, value in files.items()}, 'options': options}}}))


def prepare_dispatch(tmp_path, monkeypatch):
    data = setup(tmp_path)
    request, _, admission, original, evidence, api, helpers = data
    request_file = tmp_path / 'request.json'
    request_file.write_text(json.dumps(request))
    monkeypatch.setattr(runtime, '_client', lambda *args: api)
    monkeypatch.setattr(acceptance_snippets, 'Snippets', lambda *args, **kwargs: helpers)
    entry = tmp_path / 'environment.yml'
    files = {'recovery_request': request_file, 'original_execution_dir': original, 'cleanup_evidence_dir': evidence}
    write_entry(entry, files, {'action': 'recover'})
    args = ['--environment', str(entry), '--component', 'pve-template', '--scope', 'cohe',
            '--image-digest', request['runtime']['image_digest']]
    return data, entry, files, args


def planned_dispatch(tmp_path, monkeypatch):
    data, entry, files, args = prepare_dispatch(tmp_path, monkeypatch)
    before = {path: path.read_bytes() for path in data[3].iterdir()}
    output = tmp_path / 'planned'
    assert main(args + ['--operation', 'plan', '--output', str(output)]) == 0
    assert data[-2].new_calls == [] and data[-1].deletes == []
    assert all(path.read_bytes() == content for path, content in before.items())
    preview = output / 'plan/recovery-preview.json'
    planned = json.loads(preview.read_text())
    assert planned['reconciliation']['cleanup_eligible'] is True
    admission = data[2]
    admission['plan_digest'] = planned['preview_digest'].removeprefix('sha256:')
    admission_file = tmp_path / 'admission.json'
    admission_file.write_text(json.dumps(admission))
    files.update(recovery_preview=preview, execution_admission=admission_file)
    write_entry(entry, files, {'execution_mode': 'start'})
    return data, entry, files, args


def test_actual_recovery_plan_start_and_offline_observe_preserve_originals(tmp_path, monkeypatch, capsys):
    data, entry, files, args = planned_dispatch(tmp_path, monkeypatch)
    before = {path: path.read_bytes() for path in data[3].iterdir()}
    started = tmp_path / 'new-parent' / ID
    assert main(args + ['--operation', 'recover', '--execution-id', ID, '--output', str(started)]) == 0
    journal_root = started / 'work/pve-recovery'
    result = json.loads((journal_root / 'result.json').read_text())
    assert result['overall'] == 'passed' and result['original_acceptance'] == 'unknown'
    assert all(path.read_bytes() == content for path, content in before.items())
    original_bytes = {path: path.read_bytes() for path in journal_root.iterdir()}
    write_entry(entry, {'original_execution_dir': journal_root}, {'execution_mode': 'observe'})
    monkeypatch.setattr(runtime, '_client', lambda *args: pytest.fail('observe constructed API'))
    monkeypatch.setattr(acceptance_snippets, 'Snippets', lambda *args: pytest.fail('observe constructed helper'))
    report_args = args + ['--operation', 'recover', '--execution-id', ID]
    assert main(report_args + ['--discover']) == 0
    discovered = json.loads(capsys.readouterr().out.splitlines()[-1])
    assert discovered['credential_names'] == []
    assert not any(discovered['effects'][name] for name in ('network', 'state', 'infrastructure_write'))
    observed = tmp_path / 'observe-parent' / ID
    assert main(report_args + ['--output', str(observed)]) == 0
    assert all(path.read_bytes() == content for path, content in original_bytes.items())
    assert json.loads((observed / 'diagnostics/recovery-result.json').read_text()) == result


def test_actual_recovery_collection_failure_retains_unknown_protected_output(tmp_path, monkeypatch, capsys):
    _, _, _, args = planned_dispatch(tmp_path, monkeypatch)
    real_save = recovery.save

    def fail_export(path, value):
        if path.name == 'recovery-result.json':
            raise OSError('fixture collection unavailable')
        real_save(path, value)

    monkeypatch.setattr(recovery, 'save', fail_export)
    output = tmp_path / 'collection-failed' / ID
    assert main(args + ['--operation', 'recover', '--execution-id', ID, '--output', str(output)]) != 0
    report = json.loads(capsys.readouterr().out.splitlines()[-1])
    assert report['retain_storage'] is True
    summary = json.loads((output / 'summary.json').read_text())
    assert summary['overall'] == 'unknown' and summary['reason_code'] == 'recovery_collection_failed'
    result = json.loads((output / 'work/pve-recovery/result.json').read_text())
    assert result['collection']['status'] == 'incomplete' and result['overall'] == 'unknown'


def test_actual_missing_recovery_observation_preserves_unknown_public_outcome(tmp_path, capsys):
    original = tmp_path / 'incomplete'
    original.mkdir()
    entry = tmp_path / 'environment.yml'
    write_entry(entry, {'original_execution_dir': original}, {'execution_mode': 'observe'})
    output = tmp_path / 'collected' / ID
    assert main(['--environment', str(entry), '--component', 'pve-template', '--operation', 'recover',
                 '--execution-id', ID, '--output', str(output)]) != 0
    summary = json.loads((output / 'summary.json').read_text())
    assert summary['overall'] == 'unknown'
    assert summary['reason_code'] == 'recovery_observation_unavailable'
