from copy import deepcopy
from pathlib import Path

import pytest
import yaml

from iaas.common.errors import ValidationError
from iaas.opnsense_validation import TOP_LEVEL, validate_all, validate_document, validate_documents
from iaas.opnsense_validation.lifecycle import resource_arguments, resource_preflight
from iaas.runtime_execution.__main__ import main

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / 'tests/fixtures/opnsense-nat'
RESOURCES = ('dnat', 'one-to-one-nat', 'interface-groups')


def document(resource):
    return yaml.safe_load((FIXTURES / f'{resource}.yml').read_text())


def test_resource_identities_and_legacy_default():
    docs = {resource: document(resource) for resource in RESOURCES}
    validate_documents(docs)  # Same scope/slug in two NAT classes is valid.
    for resource, doc in docs.items():
        duplicate = deepcopy(doc)
        duplicate[TOP_LEVEL[resource]] *= 2
        with pytest.raises(ValidationError, match='duplicate managed identity'):
            validate_document(resource, duplicate)
    validate_all(ROOT / 'tests/fixtures/environment/ansible/vars/opnsense')
    with pytest.raises(ValidationError, match='unsupported resource'):
        validate_document('snat', {'opnsense_snat_rules': []})


@pytest.mark.parametrize('mode', [True, None, '', '0', 0])
def test_dnat_existing_exception_or_unknown_mode_refused(mode):
    row = document('dnat')['opnsense_dnat_rules'][0]
    existing = [{'description': 'iaas:opnsense:dnat:example:web', 'no_port_forward': mode}]
    with pytest.raises(ValidationError, match='mode'):
        resource_preflight([row], existing, 'dnat')
    absent = {'scope': row['scope'], 'slug': row['slug'], 'state': 'absent'}
    assert resource_preflight([absent], existing, 'dnat')


def test_preflight_scopes_to_declared_identity_and_checks_whole_batch():
    row = document('dnat')['opnsense_dnat_rules'][0]
    normal = {'description': 'iaas:opnsense:dnat:example:web', 'no_port_forward': False}
    assert resource_preflight([row], [normal, {'description': 'unmanaged', 'no_port_forward': True}], 'dnat')
    with pytest.raises(ValidationError, match='multiple existing'):
        resource_preflight([row], [normal, normal], 'dnat')
    with pytest.raises(ValidationError, match='mode'):
        resource_preflight([dict(row, slug='new'), row], [dict(normal, no_port_forward=True)], 'dnat')


def test_full_declaration_materializes_clears_and_defaults():
    row = document('dnat')['opnsense_dnat_rules'][0]
    del row['local_port']
    args = resource_arguments(row, 'dnat')
    assert args['local_port'] is None and args['source_port'] is None
    assert args['log'] is False and args['no_port_forward'] is False
    assert args['reload'] is False and args['match_fields'] == ['description']
    group = document('interface-groups')['opnsense_interface_groups'][0]
    del group['description']
    assert resource_arguments(group, 'interface-groups')['description'] == ''


def test_preflight_rejects_existing_external_group_as_member():
    group = document('interface-groups')['opnsense_interface_groups'][0]
    group['members'] = ['VpnGroup']
    with pytest.raises(ValidationError, match='nested interface groups'):
        resource_preflight([group], [{'name': 'VpnGroup'}], 'interface-groups')


def test_runtime_only_loads_selected_optional_resources(tmp_path, capsys):
    for resource in RESOURCES:
        (tmp_path / f'{resource}.yml').write_text(yaml.safe_dump(document(resource)))
    # Nearby deferred and unselected files must not be loaded.
    (tmp_path / 'snat.yml').write_text('invalid: [')
    entry = tmp_path / 'environment.yml'
    entry.write_text(yaml.safe_dump({'schema_version': 1, 'environment': 'synthetic', 'components': {
        'opnsense': {'inputs': {resource: f'{resource}.yml' for resource in RESOURCES}}}}))
    args = ['--environment', str(entry), '--component', 'opnsense']
    assert main([*args, '--operation', 'check', '--output', str(tmp_path / 'check')]) == 0
    assert main([*args, '--operation', 'generate', '--output', str(tmp_path / 'output')]) == 0
    generated = tmp_path / 'output/generated'
    assert {path.name for path in generated.iterdir()} == {f'{resource}.yml' for resource in RESOURCES}
    for resource in RESOURCES:
        assert yaml.safe_load((generated / f'{resource}.yml').read_text()) == document(resource)
    capsys.readouterr()
