from copy import deepcopy
import json

import pytest

from iaas_automation.common.errors import ValidationError
from iaas_automation.opnsense_workflow.contracts import load_candidate, save
from iaas_automation.opnsense_workflow.executor import reverse_documents
from test_opnsense_workflow import Appliance, TARGET, alias, candidate, documents


def _saved_candidate(tmp_path, *, device=None):
    device = device or Appliance()
    value = candidate(device, documents(aliases=[alias()]))
    path = tmp_path / "candidate.json"
    return value, path, save(path, value)


def _saved_recovery(tmp_path):
    tmp_path.mkdir(parents=True, exist_ok=True)
    device = Appliance()
    value = candidate(device, documents(aliases=[alias()]))
    from iaas_automation.opnsense_workflow.executor import apply

    apply(value, "a" * 64, device, device, "execution-1", {
        "target": TARGET, "candidate_sha256": "a" * 64,
        "execution_id": "execution-1", "checked_no_pending": True, "serialized": True,
    }, tmp_path)
    return json.loads((tmp_path / "recovery.json").read_text())


@pytest.mark.parametrize('confirmation', [None, {'rule': 'opnsense-native-aliases-v2'}])
def test_candidate_rejects_malformed_or_previous_confirmation_policy(tmp_path, confirmation):
    value, path, _ = _saved_candidate(tmp_path)
    value['stages'][0]['confirmation'] = confirmation
    reviewed = save(path, value)
    with pytest.raises(ValidationError, match='malformed candidate confirmation|re-plan'):
        load_candidate(path, reviewed)


def test_candidate_rejects_management_scope_outside_selected_execution(tmp_path):
    value, path, _ = _saved_candidate(tmp_path)
    value["request"]["managed"] = {"aliases": [["UNSELECTED"]]}
    reviewed = save(path, value)
    with pytest.raises(ValidationError, match="subset"):
        load_candidate(path, reviewed)


def test_candidate_rejects_stage_added_to_noop(tmp_path):
    value, path, _ = _saved_candidate(tmp_path, device=Appliance(aliases=[alias()]))
    value["stages"] = candidate(Appliance(), documents(aliases=[alias()]))["stages"]
    reviewed = save(path, value)
    with pytest.raises(ValidationError, match="stage"):
        load_candidate(path, reviewed)


@pytest.mark.parametrize('coverage', [[], ['aliases'], ['snat']])
def test_candidate_rejects_incomplete_or_unknown_read_coverage(tmp_path, coverage):
    value, path, _ = _saved_candidate(tmp_path)
    value['coverage'] = coverage
    reviewed = save(path, value)
    with pytest.raises(ValidationError, match='coverage'):
        load_candidate(path, reviewed)


def test_recovery_rejects_unknown_resource_and_duplicate_identity(tmp_path):
    recovery = _saved_recovery(tmp_path)
    recovery["entries"].append({**deepcopy(recovery["entries"][0]), "resource": "snat"})
    with pytest.raises(ValidationError, match="recovery|selection"):
        reverse_documents(recovery, {"schema_version": 1, "selection": {"aliases": "all"}},
                          {"aliases": {"status": "complete", "observation_scope": "configuration",
                                        "objects": []}}, TARGET)

    recovery = _saved_recovery(tmp_path / "duplicate")
    recovery["entries"].append(deepcopy(recovery["entries"][0]))
    with pytest.raises(ValidationError, match="duplicate"):
        reverse_documents(recovery, {"schema_version": 1, "selection": {"aliases": "all"}},
                          {"aliases": {"status": "complete", "observation_scope": "configuration",
                                        "objects": []}}, TARGET)


def test_recovery_rejects_invalid_standard_declaration_and_unattempted_entry(tmp_path):
    recovery = _saved_recovery(tmp_path)
    recovery["entries"][0]["desired"]["unexpected"] = True
    with pytest.raises(ValidationError):
        reverse_documents(recovery, {"schema_version": 1, "selection": {"aliases": "all"}},
                          {"aliases": {"status": "complete", "observation_scope": "configuration",
                                        "objects": []}}, TARGET)

    recovery = _saved_recovery(tmp_path / "unattempted")
    recovery["entries"][0]["attempted"] = False
    with pytest.raises(ValidationError, match="reconciled|attempted"):
        reverse_documents(recovery, {"schema_version": 1, "selection": {"aliases": "all"}},
                          {"aliases": {"status": "complete", "observation_scope": "configuration",
                                        "objects": []}}, TARGET)


def test_workflow_versions_leave_request_and_launcher_unchanged(tmp_path):
    value, path, reviewed = _saved_candidate(tmp_path)
    assert value['schema_version'] == 3
    assert value['request']['schema_version'] == 1
    assert value['runtime']['interface_version'] == 1
    assert load_candidate(path, reviewed)[0] == value
    value['schema_version'] = 1
    value.pop('admission')
    for stage in value['stages']:
        stage.pop('confirmation')
        stage.pop('content_actions')
    reviewed = save(path, value)
    with pytest.raises(ValidationError, match='re-plan'):
        load_candidate(path, reviewed)
    with pytest.raises(ValidationError, match='re-plan'):
        load_candidate(path)  # standalone verify uses the same loader


@pytest.mark.parametrize('version', [1, 2])
def test_legacy_recovery_is_rejected_even_with_activation_proof(tmp_path, version):
    recovery = _saved_recovery(tmp_path)
    assert recovery['schema_version'] == 3
    assert json.loads((tmp_path / 'result.json').read_text())['schema_version'] == 3
    recovery['schema_version'] = version
    recovery['stages'][0]['activation'] = 'confirmed'
    observed = Appliance(aliases=[alias()]).read(['aliases'])
    req = {'schema_version': 1, 'selection': {'aliases': 'all'}}
    with pytest.raises(ValidationError, match='re-plan|incompatible recovery'):
        reverse_documents(recovery, req, observed, TARGET)
