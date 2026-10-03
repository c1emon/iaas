"""Current-contract recovery binds snapshots without rewriting original evidence."""
from copy import deepcopy
import json

import pytest

from iaas.pve_acceptance_contracts import canonical_digest
from iaas.pve_template.acceptance_plan import build_preview
from iaas.pve_template.recovery_contracts import build_recovery_preview
from iaas.pve_template.recovery_evidence import reconcile_original, validate_retained_acceptance
from test_pve_acceptance_execution import finalized
from test_pve_acceptance_recovery import invoke, setup
from test_pve_acceptance_recovery_evidence import write


def test_current_recovery_cleans_full_resources_and_preserves_bytes(tmp_path):
    request, _, admission, original, evidence, api, snippets = setup(tmp_path)
    current = json.loads((original / 'request.json').read_text())
    journal = json.loads((original / 'journal.json').read_text())
    current.update(schema_version=3, cluster_scope=request['cluster_scope'], runtime=journal['runtime'],
                   vmid_policy={'acceptance': [798, 798]})
    current['temporary_vm'].update(pool='existing-old-pool', disk_size_gib=128,
                                   disk_limit_bytes=128 * 1024 ** 3 + 64 * 1024 ** 2,
                                   nameservers=['10.5.0.15'])
    current['template_record'].update(schema_version=3, cluster_scope=request['cluster_scope'], pool=None)
    preview = build_preview(current, {'readiness': {'status': 'ready'}}, image_digest=current['runtime']['image_digest'])
    journal.update(preview=preview, preview_digest=preview['preview_digest'], request_digest=canonical_digest(current))
    journal['admission'].update(schema_version=2, plan_digest=preview['preview_digest'].removeprefix('sha256:'),
                                request_digest=journal['request_digest'], runtime=journal['runtime'], recovery_of=None,
                                vmid_reservation={'cluster_scope': request['cluster_scope'], 'vmids': [798],
                                                  'reservation_id': journal['admission']['consumption']['reservation_id'],
                                                  'context_id': journal['admission']['serialization']['context_id']})
    caller = json.loads((evidence / 'caller.json').read_text())
    caller['request_digest'] = journal['request_digest']
    request['caller_association']['material'] = write(evidence, 'caller.json', caller)
    request['original_materials'] = {'request': write(original, 'request.json', current),
                                     'journal': write(original, 'journal.json', journal)}
    request['full_original_resources']['vm']['pool'] = current['temporary_vm']['pool']
    reconciled = reconcile_original(request, original, evidence, api, snippets,
                                   trusted_rejection_exports={'pve-access-export': {
                                       'sha256': request['rejection_evidence'][0]['material']['sha256'],
                                       'provenance': 'administrator_export'}})
    recovered_preview = build_recovery_preview(request, reconciled)
    admission.update(plan_digest=recovered_preview['preview_digest'].removeprefix('sha256:'),
                     request_digest=canonical_digest(request))
    before = {path: path.read_bytes() for path in original.iterdir()}
    result = invoke(tmp_path, (request, recovered_preview, admission, original, evidence, api, snippets))
    assert result['overall'] == 'passed'
    assert result['original_acceptance'] == 'unknown'
    assert all(row['existence'] == 'absent' for row in result['resources'])
    assert before == {path: path.read_bytes() for path in original.iterdir()}


@pytest.mark.parametrize('fault', [None, 'preview', 'admission', 'runtime', 'pool', 'source', 'digest', 'active'])
def test_current_retained_bindings_fail_closed(tmp_path, fault):
    _, request, journal, result = finalized(tmp_path)
    request, journal, result = deepcopy(request), deepcopy(journal), deepcopy(result)
    if fault == 'preview':
        journal['preview_digest'] = 'sha256:' + 'f' * 64
    elif fault == 'admission':
        journal['admission']['schema_version'] = 1
    elif fault == 'runtime':
        result['runtime'] = {'image_digest': 'sha256:' + 'f' * 64}
    elif fault == 'pool':
        result['pool'] = 'other-pool'
    elif fault == 'source':
        result['template']['record_id'] = 'other-source'
    elif fault == 'digest':
        journal['result_digest'] = 'sha256:' + 'f' * 64
    elif fault == 'active':
        journal['mutation_active'] = True
    if fault in {'runtime', 'pool', 'source'}:
        journal['result_digest'] = canonical_digest(result)
    if fault is None:
        validate_retained_acceptance(request, journal, result, 'accept-001')
    else:
        with pytest.raises(ValueError):
            validate_retained_acceptance(request, journal, result, 'accept-001')
