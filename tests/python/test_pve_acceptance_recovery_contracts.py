"""Current recovery exports and caller examples, without facility access."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from iaas.pve_acceptance_contracts import canonical_digest, contract_schemas as shared_schemas
from iaas.pve_template.one_shot_admission import validate_one_shot_admission
from iaas.pve_template.recovery_contracts import (
    contract_schemas, validate_recovery_request, validate_recovery_preview, validate_recovery_result,
)
from iaas.pve_template.recovery_evidence import load_original

ROOT = Path(__file__).resolve().parents[2]
EXAMPLES = ROOT / 'docs/examples/recovery'
VALIDATORS = {'pve-acceptance-recovery-request': validate_recovery_request,
              'pve-acceptance-recovery-preview': validate_recovery_preview,
              'pve-acceptance-recovery-result': validate_recovery_result}


def test_recovery_schema_exports_are_current():
    for name, schema in contract_schemas().items():
        path = ROOT / 'automation/schemas/pve-acceptance-recovery/v1' / (name + '.schema.json')
        assert json.loads(path.read_text()) == schema


@pytest.mark.parametrize('filename,validator', [
    ('recovery-request.json', validate_recovery_request),
    ('recovery-preview.json', validate_recovery_preview),
    ('recovery-result.json', validate_recovery_result),
])
def test_caller_reference_namespaces_are_preserved(filename, validator):
    document = json.loads((EXAMPLES / filename).read_text())
    request = document['fixed_input'] if 'fixed_input' in document else document
    association = request['caller_association']
    association['pending_record_id'] = 'astra-pve-template:' + association['execution_id']
    association['reservation_id'] = 'run-120-1:' + association['execution_id']
    if 'fixed_input' in document:
        document['request_digest'] = canonical_digest(request)
        document['preview_digest'] = canonical_digest({k: v for k, v in document.items() if k != 'preview_digest'})
    assert validator(document) == document
    jsonschema = pytest.importorskip('jsonschema')
    jsonschema.Draft202012Validator(contract_schemas()[document['kind']]).validate(document)


@pytest.mark.parametrize('field', ['plan_id', 'execution_id'])
def test_caller_execution_identifiers_do_not_allow_reference_separators(field):
    document = json.loads((EXAMPLES / 'recovery-request.json').read_text())
    document['caller_association'][field] = 'namespace:value'
    with pytest.raises(ValueError):
        validate_recovery_request(document)


def test_examples_have_current_structural_and_digest_bindings():
    jsonschema = pytest.importorskip('jsonschema')
    request = json.loads((EXAMPLES / 'recovery-request.json').read_text())
    preview = json.loads((EXAMPLES / 'recovery-preview.json').read_text())
    result = json.loads((EXAMPLES / 'recovery-result.json').read_text())
    for value in (request, preview, result):
        assert VALIDATORS[value['kind']](value) == value
        jsonschema.Draft202012Validator(contract_schemas()[value['kind']]).validate(value)
    admission = json.loads((EXAMPLES / 'recovery-admission.json').read_text())
    jsonschema.Draft202012Validator(shared_schemas()['pve-one-shot-execution-admission']).validate(admission)
    validate_one_shot_admission(admission, request=request, preview=preview, execution_id=admission['execution_id'],
                               image_digest=request['runtime']['image_digest'], vmids=[798],
                               recovery_of=request['original_execution_id'])
    assert preview['request_digest'] == result['request_digest'] == canonical_digest(request)
    assert result['preview_digest'] == preview['preview_digest']
    originals = load_original(request, EXAMPLES / 'original', EXAMPLES / 'evidence')
    assert originals['request']['schema_version'] == 2
    assert originals['request']['template_record']['schema_version'] == 2
    assert originals['request']['temporary_vm']['vmid'] == 798
    assert 'pool' not in originals['request']['temporary_vm']
    assert result['original_acceptance'] == 'unknown'


@pytest.mark.parametrize('filename,validator', [
    ('recovery-request.json', validate_recovery_request),
    ('recovery-preview.json', validate_recovery_preview),
    ('recovery-result.json', validate_recovery_result),
])
def test_recovery_validation_errors_do_not_echo_protected_inputs(filename, validator):
    document = json.loads((EXAMPLES / filename).read_text())
    document['credential'] = 'protected-input-sentinel'
    with pytest.raises(ValueError) as error:
        validator(document)
    assert 'protected-input-sentinel' not in str(error.value)
    assert 'credential' not in str(error.value)


def test_passed_result_requires_complete_absent_resource_list():
    document = json.loads((EXAMPLES / 'recovery-result.json').read_text())
    for mutate in (lambda d: d['resources'].pop(),
                   lambda d: d['resources'][0].update(existence='unknown'),
                   lambda d: d['reconciliation'].update(active_tasks=True),
                   lambda d: d['reconciliation'].update(task_activity_unresolved=True),
                   lambda d: d.update(facility_writes='unknown')):
        changed = deepcopy(document)
        mutate(changed)
        with pytest.raises(ValueError):
            validate_recovery_result(changed)


def test_cleanup_success_preserves_historical_unknown():
    document = json.loads((EXAMPLES / 'recovery-result.json').read_text())
    document.update(original_activity='unknown', original_facility_writes='unknown')
    result = validate_recovery_result(document)
    assert result['overall'] == 'passed'
    assert result['original_acceptance'] == 'unknown'


@pytest.mark.parametrize('mode,operation', [('plan', 'plan'), ('start', 'recover'), ('observe', 'recover')])
def test_environment_examples_select_exact_readonly_maps(tmp_path, mode, operation):
    import yaml
    from iaas.runtime_config import SourceReader
    from iaas.runtime_execution.selection import load_operation
    environment = yaml.safe_load((EXAMPLES / ('environment-' + mode + '.yml')).read_text())
    files = environment['components']['pve-template']['files']
    for alias, filename in list(files.items()):
        if alias == 'original_execution_dir':
            files[alias] = str(EXAMPLES / 'original')
        elif alias == 'cleanup_evidence_dir':
            files[alias] = str(EXAMPLES / 'evidence')
        elif alias in {'api_ca', 'ssh_key', 'known_hosts'}:
            path = tmp_path / alias
            path.write_text('isolated synthetic file\n')
            files[alias] = str(path)
        else:
            files[alias] = str(EXAMPLES / filename)
    entry = tmp_path / 'environment.yml'
    entry.write_text(yaml.safe_dump(environment))
    selected = load_operation(entry, 'pve-template', operation, None, SourceReader())
    if mode == 'plan':
        assert set(selected.files) == {'recovery_request', 'original_execution_dir', 'cleanup_evidence_dir', 'api_ca', 'ssh_key', 'known_hosts'}
        assert 'execution_admission' not in selected.files
    elif mode == 'start':
        assert {'recovery_preview', 'execution_admission'} <= selected.files.keys()
    else:
        assert set(selected.files) == {'original_execution_dir'}
        from iaas.runtime_execution.operations import capabilities
        effects = capabilities()['execution_modes']['pve-template']['recover']['observe']
        assert effects['network'] is False
        assert effects['infrastructure_write'] is False
