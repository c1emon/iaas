"""Shared caller/runtime fixtures are synthetic software evidence, never live acceptance."""
import copy
import json
from pathlib import Path

import pytest

from iaas.pve_acceptance_contracts import (
    canonical_digest, contract_schemas, load_strict_json,
    validate_acceptance_request, validate_acceptance_result,
    validate_snippet_cleanup_request, validate_snippet_cleanup_result,
)

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / 'docs/examples/pve-acceptance'
CASES = json.loads((FIXTURES / 'cases.json').read_text())['cases']
VALIDATORS = {
    'pve-template-acceptance-request': validate_acceptance_request,
    'pve-template-acceptance-result': validate_acceptance_result,
    'pve-snippet-cleanup-request': validate_snippet_cleanup_request,
    'pve-snippet-cleanup-result': validate_snippet_cleanup_result,
}


@pytest.mark.parametrize('case', CASES, ids=lambda case: case['file'])
def test_shared_contract_fixture(case):
    document = load_strict_json(FIXTURES / case['file'])
    if case['valid']:
        assert VALIDATORS[case['kind']](document) == document
    else:
        with pytest.raises(ValueError):
            VALIDATORS[case['kind']](document)


def test_schema_exports_are_current():
    for name, schema in contract_schemas().items():
        path = ROOT / 'automation/schemas/pve-acceptance/v2' / f'{name}.schema.json'
        assert json.loads(path.read_text()) == schema


def test_positive_fixtures_conform_to_exported_schemas():
    jsonschema = pytest.importorskip('jsonschema')
    for case in CASES:
        if case['valid']:
            document = load_strict_json(FIXTURES / case['file'])
            jsonschema.Draft202012Validator(contract_schemas()[case['kind']]).validate(document)


def test_duplicate_keys_and_float_deadlines_fail(tmp_path):
    path = tmp_path / 'request.json'
    for content in ('{"kind":"x","kind":"y"}', '{"timeout_seconds":NaN}', '{"timeout_seconds":1.2}'):
        path.write_text(content)
        with pytest.raises(ValueError):
            load_strict_json(path)


def test_retry_cannot_refer_to_current_execution():
    request = load_strict_json(FIXTURES / 'cleanup-retry-request.json')
    with pytest.raises(ValueError, match='retry itself'):
        validate_snippet_cleanup_request(request, execution_id=request['retry_of'])


def test_request_digest_order_independent_and_scope_sensitive():
    request = load_strict_json(FIXTURES / 'cleanup-acceptance-request.json')
    assert canonical_digest(request) == canonical_digest(dict(reversed(list(request.items()))))
    changed = copy.deepcopy(request)
    changed['snippets'][0]['sha256'] = 'f' * 64
    assert canonical_digest(request) != canonical_digest(changed)


def test_bool_schema_version_and_unknown_fields_rejected():
    request = load_strict_json(FIXTURES / 'acceptance-request.json')
    for mutate in (lambda d: d.update(schema_version=True),
                   lambda d: d['temporary_vm'].update(shell='unsafe'),
                   lambda d: d.update(token='private-test-sentinel')):
        changed = copy.deepcopy(request)
        mutate(changed)
        with pytest.raises(ValueError) as error:
            validate_acceptance_request(changed)
        assert 'private-test-sentinel' not in str(error.value)


@pytest.mark.parametrize('host', ['pve.example.invalid', '10.1.0.5', '2001:db8::5', '::1'])
def test_cleanup_binds_supported_ssh_endpoint(host):
    request = load_strict_json(FIXTURES / 'cleanup-acceptance-request.json')
    original_digest = canonical_digest(request)
    request['ssh']['host'] = host
    assert validate_snippet_cleanup_request(request)['ssh']['host'] == host
    if host != 'pve.example.invalid':
        assert canonical_digest(request) != original_digest


@pytest.mark.parametrize('connection', [
    {'host': '-oProxyCommand=unsafe', 'user': 'iaas', 'port': 22},
    {'host': 'user@pve.example.invalid', 'user': 'iaas', 'port': 22},
    {'host': 'pve.example.invalid/path', 'user': 'iaas', 'port': 22},
    {'host': '999.1.1.1', 'user': 'iaas', 'port': 22},
    {'host': 'pve.example.invalid', 'user': 'root', 'port': 22},
    {'host': 'pve.example.invalid', 'user': 'iaas -oUnsafe', 'port': 22},
    {'host': 'pve.example.invalid', 'user': 'iaas', 'port': 0},
    {'host': 'pve.example.invalid', 'user': 'iaas', 'port': 65536},
    {'host': 'pve.example.invalid', 'user': 'iaas', 'port': True},
])
def test_cleanup_rejects_unbounded_or_unsafe_ssh_connection(connection):
    request = load_strict_json(FIXTURES / 'cleanup-acceptance-request.json')
    request['ssh'] = connection
    with pytest.raises(ValueError):
        validate_snippet_cleanup_request(request)
