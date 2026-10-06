"""Resource-scoped audit metadata over synthetic read and plan boundaries."""
from copy import deepcopy
import json

import pytest

from iaas.common.errors import ValidationError
from iaas.opnsense_validation import TOP_LEVEL
from iaas.opnsense_workflow.planning import plan
from iaas.opnsense_workflow.presentation import project_observations
from test_opnsense_workflow_reader import COLLECTION_TARGETS, TARGET, FakeCollection, reader


pytestmark = pytest.mark.fast
RUNTIME = {'image_digest': 'registry.invalid/runtime@sha256:' + 'a' * 64,
           'platform': 'linux/arm64', 'interface_version': 1}


@pytest.mark.parametrize('resource', ['filter-rules', 'dnat', 'one-to-one-nat'])
def test_audit_preserves_configuration_and_unchanged_plan_without_identity_output(resource, caplog, capsys):
    transport = FakeCollection()
    baseline = reader(transport).read(list(COLLECTION_TARGETS))
    obj = baseline[resource]['objects'][0]
    expected = deepcopy(obj['configuration'])
    assert expected is not None
    documents = {resource: {TOP_LEVEL[resource]: [expected]}}
    request = {'schema_version': 1, 'selection': {resource: 'all'},
               'managed': {resource: [obj['identity']]}}
    original = plan(documents, request, baseline, TARGET, RUNTIME, {'inputs': []})

    # JsonAuditField emits serialized JSON; also cover an already decoded value.
    for audit in (
        json.dumps({'created': {'username': 'AUDIT_CREATOR', 'timestamp': 1}}),
        {'created': {'username': 'AUDIT_CREATOR', 'timestamp': 1},
         'updated': {'username': 'AUDIT_EDITOR', 'timestamp': 2}},
    ):
        transport.rows[resource][0]['audit'] = audit
        before = deepcopy(transport.rows)
        observed = reader(transport).read(list(COLLECTION_TARGETS))
        assert observed == baseline
        assert observed[resource]['objects'][0]['configuration'] == expected
        candidate = plan(documents, request, observed, TARGET, RUNTIME, {'inputs': []})
        assert candidate == original
        assert candidate['differences'][0]['action'] == 'unchanged'
        display = project_observations(observed, request['selection'])
        exported = json.dumps([observed, candidate, display])
        assert 'audit' not in exported
        assert 'AUDIT_CREATOR' not in exported
        assert 'AUDIT_EDITOR' not in exported
        assert transport.rows == before
        assert not transport.mutated

    captured = capsys.readouterr()
    output = caplog.text + captured.out + captured.err
    assert 'AUDIT_CREATOR' not in output
    assert 'AUDIT_EDITOR' not in output


@pytest.mark.parametrize('resource', ['filter-rules', 'dnat', 'one-to-one-nat'])
def test_audit_does_not_hide_unknown_configuration_or_allow_plan(resource):
    transport = FakeCollection()
    baseline = reader(transport).read(list(COLLECTION_TARGETS))
    obj = baseline[resource]['objects'][0]
    documents = {resource: {TOP_LEVEL[resource]: [obj['configuration']]}}
    request = {'schema_version': 1, 'selection': {resource: 'all'},
               'managed': {resource: [obj['identity']]}}
    transport.rows[resource][0].update(
        audit={'updated': {'username': 'AUDIT_EDITOR', 'timestamp': 2}},
        unsupported_config='UNSUPPORTED_VALUE',
    )
    observed = reader(transport).read(list(COLLECTION_TARGETS))
    item = observed[resource]['objects'][0]
    assert item['configuration'] is None
    assert item['reason'] == 'unexpressed_native_fields:unknown_native_field'
    with pytest.raises(ValidationError, match='selected native configuration is unsupported'):
        plan(documents, request, observed, TARGET, RUNTIME, {'inputs': []})
    assert 'AUDIT_EDITOR' not in json.dumps(observed)
    assert 'UNSUPPORTED_VALUE' not in json.dumps(observed)


@pytest.mark.parametrize('resource', ['aliases', 'vips', 'gateways', 'interface-groups'])
def test_audit_exception_is_not_global(resource):
    transport = FakeCollection()
    transport.rows[resource][0]['audit'] = {'updated': {'username': 'AUDIT_EDITOR'}}
    item = reader(transport).read([resource])[resource]['objects'][0]
    assert item['configuration'] is None
    assert item['reason'] == 'unexpressed_native_fields:unknown_native_field'


@pytest.mark.parametrize('resource,metadata', [
    ('one-to-one-nat', {'sort_order': '1000001', 'prio_group': '200'}),
    ('vips', {'vhid_txt': 'DERIVED_DISPLAY'}),
])
def test_known_display_metadata_preserves_configuration_but_unknowns_block(resource, metadata):
    transport = FakeCollection()
    baseline = reader(transport).read(list(COLLECTION_TARGETS))
    obj = baseline[resource]['objects'][0]
    documents = {resource: {TOP_LEVEL[resource]: [obj['configuration']]}}
    request = {'schema_version': 1, 'selection': {resource: 'all'},
               'managed': {resource: [obj['identity']]}}
    original = plan(documents, request, baseline, TARGET, RUNTIME, {'inputs': []})
    transport.rows[resource][0].update(metadata)
    observed = reader(transport).read(list(COLLECTION_TARGETS))
    assert observed == baseline
    assert plan(documents, request, observed, TARGET, RUNTIME, {'inputs': []}) == original
    transport.rows[resource][0]['unsupported_config'] = 'UNSUPPORTED'
    observed = reader(transport).read(list(COLLECTION_TARGETS))
    assert observed[resource]['objects'][0]['configuration'] is None
    with pytest.raises(ValidationError, match='selected native configuration is unsupported'):
        plan(documents, request, observed, TARGET, RUNTIME, {'inputs': []})
