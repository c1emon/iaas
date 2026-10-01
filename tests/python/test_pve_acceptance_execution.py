"""Durable one-shot bindings; no PVE/backend/network calls are involved."""
import copy
from pathlib import Path

import pytest

from iaas.pve_acceptance_contracts import canonical_digest, load_strict_json
from iaas.pve_template.acceptance_execution import begin, confined, observe, save
from iaas.pve_template.acceptance_plan import build_preview

FIXTURES = Path(__file__).resolve().parents[2] / 'docs/examples/pve-acceptance'


def materials():
    request = load_strict_json(FIXTURES / 'acceptance-request.json')
    preview = build_preview(request, {'readiness': {'status': 'ready'}}, image_digest=request['runtime']['image_digest'])
    admission = {
        'schema_version': 2, 'execution_id': 'accept-001',
        'plan_digest': preview['preview_digest'].removeprefix('sha256:'),
        'request_digest': canonical_digest(request), 'runtime': request['runtime'],
        'vmid_reservation': {'cluster_scope': request['cluster_scope'], 'vmids': [request['temporary_vm']['vmid']],
                             'reservation_id': 'reservation-001', 'context_id': 'complete-workflow-lock'},
        'target': request['target'], 'deadlines': request['deadlines'], 'approved': True,
        'consumption': {'reserved': True, 'reservation_id': 'reservation-001'},
        'pending': {'record_id': 'pending-001'},
        'serialization': {'held': True, 'context_id': 'complete-workflow-lock'},
    }
    return request, admission


def preview(request):
    return build_preview(request, {'readiness': {'status': 'ready'}}, image_digest=request['runtime']['image_digest'])


def started(tmp_path):
    request, admission = materials()
    root = tmp_path / 'original'
    journal = begin(root, 'accept', request, admission, 'accept-001', 'sha256:' + 'e' * 64, preview=preview(request))
    return root, request, journal


def test_start_persists_private_binding_and_observe_never_changes_original(tmp_path):
    root, request, journal = started(tmp_path)
    before = {path.name: path.read_bytes() for path in root.iterdir()}
    assert observe(root, 'accept', request, 'accept-001') == (journal, None)
    assert before == {path.name: path.read_bytes() for path in root.iterdir()}
    assert all(path.stat().st_mode & 0o077 == 0 for path in root.iterdir())
    assert journal['admission']['consumption']['reservation_id'] == 'reservation-001'
    assert journal['mutation_active'] is False


def test_repeat_start_refuses_without_overwriting(tmp_path):
    root, request, _ = started(tmp_path)
    _, admission = materials()
    before = (root / 'journal.json').read_bytes()
    with pytest.raises((ValueError, FileExistsError)):
        begin(root, 'accept', request, admission, 'accept-001', 'sha256:' + 'e' * 64, preview=preview(request))
    assert (root / 'journal.json').read_bytes() == before


def test_legacy_start_refused_before_creating_execution_state(tmp_path):
    request, admission = materials()
    request['schema_version'] = 2
    root = tmp_path / 'legacy'
    with pytest.raises(ValueError):
        begin(root, 'accept', request, admission, 'accept-001', 'sha256:' + 'e' * 64, preview=preview(request))
    assert not root.exists()


def test_start_refuses_existing_material_even_if_marker_missing(tmp_path):
    root, request, _ = started(tmp_path)
    (root / 'started').unlink(missing_ok=True)
    _, admission = materials()
    with pytest.raises((ValueError, FileExistsError)):
        begin(root, 'accept', request, admission, 'accept-001', 'sha256:' + 'e' * 64, preview=preview(request))


@pytest.mark.parametrize('which', ['directory', 'request.json', 'journal.json'])
def test_missing_original_material_refuses_observation(tmp_path, which):
    if which == 'directory':
        root = tmp_path / 'missing'
        request, _ = materials()
    else:
        root, request, _ = started(tmp_path)
        (root / which).unlink()
    with pytest.raises(ValueError):
        observe(root, 'accept', request, 'accept-001')


@pytest.mark.parametrize('change', ['request', 'execution', 'operation', 'target', 'digest', 'reservation', 'pending'])
def test_observation_conflicts_fail_closed(tmp_path, change):
    root, request, journal = started(tmp_path)
    operation, execution = 'accept', 'accept-001'
    if change == 'request':
        request = copy.deepcopy(request)
        request['temporary_vm']['vmid'] += 1
    elif change == 'execution':
        execution = 'accept-other'
    elif change == 'operation':
        operation = 'snippet-cleanup'
    elif change == 'target':
        journal['target'] = {**journal['target'], 'node': 'other'}
    elif change == 'digest':
        journal['request_digest'] = 'sha256:' + 'f' * 64
    elif change == 'reservation':
        journal['admission']['consumption'].pop('reservation_id')
    elif change == 'pending':
        journal['admission']['pending'].pop('record_id')
    save(root / 'journal.json', journal)
    with pytest.raises(ValueError):
        observe(root, operation, request, execution)


def finalized(tmp_path):
    root, request, journal = started(tmp_path)
    result = load_strict_json(FIXTURES / 'acceptance-result.json')
    result['preview_digest'] = journal['preview_digest']
    result['capacity'] = None
    journal.update(status='finished', mutation_active=False, facility_writes='issued', result_digest=canonical_digest(result))
    save(root / 'journal.json', journal)
    save(root / 'result.json', result)
    return root, request, journal, result


def test_terminal_result_requires_original_digest_and_runtime(tmp_path):
    root, request, journal, result = finalized(tmp_path)
    assert observe(root, 'accept', request, 'accept-001') == (journal, result)


@pytest.mark.parametrize('field', ['runtime', 'request_digest', 'execution_id', 'result_digest', 'active'])
def test_terminal_result_mismatch_rejected(tmp_path, field):
    root, request, journal, result = finalized(tmp_path)
    if field == 'runtime':
        result['runtime'] = {'image_digest': 'sha256:' + 'f' * 64}
        journal['result_digest'] = canonical_digest(result)
    elif field == 'request_digest':
        result[field] = 'sha256:' + 'f' * 64
    elif field == 'execution_id':
        result[field] = 'other'
    elif field == 'result_digest':
        journal[field] = 'sha256:' + 'f' * 64
    else:
        journal['mutation_active'] = True
    save(root / 'journal.json', journal)
    save(root / 'result.json', result)
    with pytest.raises(ValueError):
        observe(root, 'accept', request, 'accept-001')


def test_evidence_paths_reject_escape_and_symlink(tmp_path):
    root, _, _ = started(tmp_path)
    (root / 'link').symlink_to(root / 'request.json')
    for relative in ('../outside', '/etc/passwd', 'link'):
        with pytest.raises(ValueError):
            confined(root, relative)


@pytest.mark.parametrize('status', ['running', 'interrupted', 'finished'])
def test_observe_exposes_bound_unknown_result_while_task_active(tmp_path, status):
    root, request, journal, result = finalized(tmp_path)
    result['overall'] = 'unknown'
    result['checks'][0].update(status='unknown', reason_code='task_unknown')
    result['failure_stage'] = 'full_clone'
    journal.update(status=status, mutation_active=True, result_digest=canonical_digest(result))
    save(root / 'journal.json', journal)
    save(root / 'result.json', result)
    before = {path.name: path.read_bytes() for path in root.iterdir()}
    observed_journal, observed_result = observe(root, 'accept', request, 'accept-001')
    assert observed_journal['mutation_active'] is True
    assert observed_result['checks'][0]['status'] == 'unknown'
    assert before == {path.name: path.read_bytes() for path in root.iterdir()}


@pytest.mark.parametrize('fault', ['missing_preview', 'legacy_admission', 'preview_digest', 'request_digest', 'runtime', 'reservation'])
def test_current_start_requires_reviewed_preview_and_v2_association_before_state(tmp_path, fault):
    request, admission = materials()
    planned = preview(request)
    digest = request['runtime']['image_digest']
    if fault == 'missing_preview':
        planned = None
    elif fault == 'legacy_admission':
        admission['schema_version'] = 1
    elif fault == 'preview_digest':
        admission['plan_digest'] = 'f' * 64
    elif fault == 'request_digest':
        admission['request_digest'] = 'sha256:' + 'f' * 64
    elif fault == 'runtime':
        digest = 'sha256:' + 'f' * 64
    else:
        admission['vmid_reservation']['vmids'] = [9101]
    root = tmp_path / 'refused'
    with pytest.raises(ValueError):
        begin(root, 'accept', request, admission, 'accept-001', digest, preview=planned)
    assert not root.exists()


@pytest.mark.parametrize('fault', ['preview_file', 'journal_preview', 'journal_preview_digest', 'missing_preview'])
def test_observe_checks_current_preview_snapshot_without_rewriting(tmp_path, fault):
    root, request, journal = started(tmp_path)
    if fault == 'missing_preview':
        (root / 'preview.json').unlink()
    elif fault == 'preview_file':
        planned = load_strict_json(root / 'preview.json')
        planned['observed']['readiness']['pool'] = 'another-pool'
        save(root / 'preview.json', planned)
    elif fault == 'journal_preview':
        journal['preview']['runtime']['image_digest'] = 'sha256:' + 'f' * 64
        save(root / 'journal.json', journal)
    else:
        journal['preview_digest'] = 'sha256:' + 'f' * 64
        save(root / 'journal.json', journal)
    before = {path.name: path.read_bytes() for path in root.iterdir()}
    with pytest.raises(ValueError):
        observe(root, 'accept', request, 'accept-001')
    assert before == {path.name: path.read_bytes() for path in root.iterdir()}
