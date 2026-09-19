"""Representative workflow invariants over synthetic appliance observations."""
from copy import deepcopy
import json

import pytest

from iaas_automation.common.errors import ValidationError
from iaas_automation.opnsense_validation import TOP_LEVEL
from iaas_automation.opnsense_workflow.contracts import identity, key, load_candidate, request, save
from iaas_automation.opnsense_workflow.executor import apply, reverse_documents, verify
from iaas_automation.opnsense_workflow.planning import coverage, plan


TARGET = {'host': 'firewall-a', 'endpoint': 'https://192.0.2.254', 'ssl_verify': True}
RUNTIME = {'image_digest': 'registry.invalid/runtime@sha256:' + 'a' * 64,
           'platform': 'linux/arm64', 'interface_version': 1}


def alias(name='A', content=None, **extra):
    return {'name': name, 'type': 'network', 'content': content or ['192.0.2.0/24'],
            'description': 'synthetic', 'enabled': True, 'state': 'present', **extra}


def rule(destination='A', **extra):
    return {'scope': 'example', 'slug': 'allow', 'state': 'present', 'enabled': True,
            'sequence': 100, 'interface': ['lan'], 'direction': 'in', 'action': 'pass',
            'quick': True, 'ip_protocol': 'inet', 'protocol': 'TCP',
            'source_net': ['any'], 'destination_net': [destination], **extra}


def documents(**resources):
    return {resource.replace('_', '-'): {TOP_LEVEL[resource.replace('_', '-')]: rows}
            for resource, rows in resources.items()}


class Appliance:
    def __init__(self, **resources):
        self.resources = {name.replace('_', '-'): deepcopy(rows) for name, rows in resources.items()}
        self.calls = []
        self.pending = 'unknown'
        self.activation = 'confirmed'
        self.save_failure = False
        self.unreadable = False

    def read(self, resources):
        return {resource: {'status': 'failed' if self.unreadable else 'complete', 'interfaces': ['lan', 'wan'],
                           # Synthetic completion adapter exercises orchestration, not appliance support.
                           'confirmation_capability': {'activation_completion': 'available',
                               'source_processing': 'available', 'content_loading': 'available',
                               'basis': 'synthetic action completion'},
                           'objects': [{'identity': identity(resource, row), 'configuration': deepcopy(row),
                                        'recovery': 'expressible'} for row in self.resources.get(resource, [])]}
                for resource in resources}

    def pending_changes(self):
        return {'status': self.pending}

    def save(self, resource, records):
        self.calls.append(('save', resource))
        for row in records:
            rows = self.resources.setdefault(resource, [])
            rows[:] = [old for old in rows if identity(resource, old) != identity(resource, row)]
            if row['state'] == 'present':
                rows.append(deepcopy(row))
        if self.save_failure:
            return {'status': 'unknown'}
        return {'status': 'saved'}

    def activate(self, resource):
        self.calls.append(('activate', resource))
        return {'status': self.activation}


def candidate(device, docs, *, selection=None, managed=None, **req):
    selection = selection if selection is not None else {resource: 'all' for resource in docs}
    if managed is None:
        managed = {resource: [identity(resource, row) for row in document[TOP_LEVEL[resource]]]
                   for resource, document in docs.items()}
    req = {'schema_version': 1, 'selection': selection, 'managed': managed, **req}
    return plan(docs, req, device.read(list(TOP_LEVEL)), TARGET, RUNTIME, {'inputs': []})


def execute(tmp_path, device, cand, conclusion=None):
    return apply(cand, 'a' * 64, device, device, 'execution-1', conclusion if conclusion is not None else {
        'target': TARGET, 'candidate_sha256': 'a' * 64, 'execution_id': 'execution-1',
        'checked_no_pending': True, 'serialized': True,
    }, tmp_path)


def test_fixed_candidate_and_digest(tmp_path):
    docs = documents(aliases=[alias()])
    cand = candidate(Appliance(), docs)
    path = tmp_path / 'candidate.json'
    reviewed = save(path, cand)
    docs['aliases'][TOP_LEVEL['aliases']][0]['content'] = ['203.0.113.0/24']
    assert load_candidate(path, reviewed)[0]['selected'][0]['desired']['content'] == ['192.0.2.0/24']
    path.write_text(path.read_text() + ' ')
    with pytest.raises(ValidationError, match='digest'):
        load_candidate(path, reviewed)


def test_live_rule_without_recreation_context_is_manual_recovery():
    from iaas_automation.opnsense_workflow.executor import recovery_document
    device = Appliance(filter_rules=[rule('192.0.2.0/24', action='block', protocol='any', destination_invert=True)])
    cand = candidate(device, documents(filter_rules=[rule('192.0.2.10')]))
    recovery = recovery_document(cand, 'a' * 64, 'execution-1', cand['before'])
    assert recovery['entries'][0]['before']['action'] == 'block'
    assert recovery['entries'][0]['recovery'] == 'manual_required'


@pytest.mark.parametrize('bad', [
    {'schema_version': 1}, {'schema_version': 1, 'selection': {'snat': 'all'}},
    {'schema_version': 1, 'selection': {}, 'site_policy': {}},
    {'schema_version': 1, 'selection': {'aliases': [['A'], ['A']]}},
    {'schema_version': True, 'selection': {}},
])
def test_request_rejects_unknown_or_ambiguous(bad):
    with pytest.raises(ValidationError):
        request(bad)


def test_explicit_empty_and_unselected_preserved(tmp_path):
    device = Appliance(aliases=[alias('unmanaged')])
    cand = candidate(device, documents(aliases=[]))
    result = execute(tmp_path, device, cand, {})
    assert result['status'] == 'fully_verified'
    assert device.calls == [] and device.resources['aliases'][0]['name'] == 'unmanaged'


def test_existing_identity_needs_adoption():
    device = Appliance(aliases=[alias()])
    docs = documents(aliases=[alias(content=['203.0.113.0/24'])])
    with pytest.raises(ValidationError, match='adoption'):
        candidate(device, docs, managed={})
    cand = candidate(device, docs, managed={}, adopt={'aliases': [['A']]})
    assert cand['differences'][0]['adopted'] is True


def test_native_interface_address_token_requires_observed_interface(tmp_path):
    device = Appliance()
    cand = candidate(device, documents(filter_rules=[rule('wanip')]))
    assert execute(tmp_path, device, cand)['status'] == 'completed_with_unverified'
    with pytest.raises(ValidationError, match='missing dependency'):
        candidate(Appliance(), documents(filter_rules=[rule('missingip')]))


@pytest.mark.parametrize('resource', list(TOP_LEVEL))
def test_seven_resource_semantic_updates_preserve_other_objects(tmp_path, resource):
    from test_opnsense_workflow_reader import FakeCollection, reader, ROWS
    observed = reader(FakeCollection()).read(list(ROWS))
    actual = {name: [obj['configuration'] for obj in value['objects']] for name, value in observed.items()}
    device = Appliance(**actual)
    changed = deepcopy(actual[resource][0])
    if resource in {'filter-rules', 'dnat', 'one-to-one-nat'}:
        changed['sequence'] += 1
    else:
        changed['description'] = 'reviewed update'
    cand = candidate(device, {resource: {TOP_LEVEL[resource]: [changed]}})
    assert cand['differences'][0]['action'] == 'update'
    assert execute(tmp_path, device, cand)['status'] == 'completed_with_unverified'
    assert all(device.resources[name] == rows for name, rows in actual.items() if name != resource)


def test_create_switch_retire_and_reverse_reference_rejection(tmp_path):
    device = Appliance(aliases=[alias('A')], filter_rules=[rule()])
    docs = documents(aliases=[alias('A', state='absent'), alias('B')], filter_rules=[rule('B')])
    with pytest.raises(ValidationError, match='dependency|transition'):
        candidate(device, docs, selection={'aliases': [['A']]}, managed={'aliases': [['A']]})
    cand = candidate(device, docs)
    assert [stage['resource'] for stage in cand['stages']] == ['aliases', 'filter-rules', 'aliases']
    result = execute(tmp_path, device, cand)
    assert result['status'] == 'completed_with_unverified'
    assert [row['name'] for row in device.resources['aliases']] == ['B']
    assert device.resources['filter-rules'][0]['destination_net'] == ['B']


def test_new_identity_and_reference_drift_before_first_write(tmp_path):
    device = Appliance()
    cand = candidate(device, documents(aliases=[alias()]))
    device.resources['aliases'] = [alias(content=['203.0.113.0/24'])]
    assert execute(tmp_path, device, cand)['status'] == 'failed'
    assert device.calls == []


def test_unselected_reference_appears_is_drift(tmp_path):
    device = Appliance(aliases=[alias()])
    cand = candidate(device, documents(aliases=[alias(state='absent')]))
    device.resources['filter-rules'] = [rule()]
    assert execute(tmp_path, device, cand)['status'] == 'failed'
    assert not device.calls


@pytest.mark.parametrize('pending,conclusion', [('conflict', None), ('unknown', {}),
                                              ('unknown', {'execution_id': 'old-execution'})])
def test_shared_activation_admission(tmp_path, pending, conclusion):
    device = Appliance()
    cand = candidate(device, documents(aliases=[alias()]))
    device.pending = pending
    result = execute(tmp_path, device, cand, conclusion)
    assert result['status'] == 'failed' and device.calls == []


@pytest.mark.parametrize('outcome', ['failed', 'accepted', 'unconfirmed'])
def test_activation_failure_stops_dependency_stage(tmp_path, outcome):
    device = Appliance()
    cand = candidate(device, documents(aliases=[alias()], filter_rules=[rule()]))
    device.activation = outcome
    result = execute(tmp_path, device, cand)
    assert result['status'] == 'failed'
    assert device.calls == [('save', 'aliases'), ('activate', 'aliases')]
    assert result['stages'][0]['save'] == 'saved'
    recovery = json.loads((tmp_path / 'recovery.json').read_text())
    assert recovery['entries'][0]['after_status'] == 'confirmed'


def test_partial_save_and_unavailable_readback(tmp_path):
    device = Appliance()
    cand = candidate(device, documents(aliases=[alias()]))
    device.save_failure = True
    result = execute(tmp_path, device, cand)
    assert result['status'] == 'failed' and device.calls == [('save', 'aliases')]
    assert result['stages'][0]['activation'] == 'not_attempted'


def test_absent_verify_and_ordinary_noop(tmp_path):
    device = Appliance(aliases=[alias()])
    cand = candidate(device, documents(aliases=[alias()]))
    assert execute(tmp_path, device, cand)['status'] == 'completed_with_unverified'
    assert not device.calls
    deleted = candidate(device, documents(aliases=[alias(state='absent')]))
    assert verify(deleted, device)['status'] == 'failed'
    device.resources['aliases'] = []
    assert verify(deleted, device)['objects'][0]['configuration'] == 'verified'


def test_explicit_activation_recovery(tmp_path):
    device = Appliance(aliases=[alias()])
    cand = candidate(device, documents(aliases=[alias()]), activation_recovery={'aliases': [['A']]})
    assert execute(tmp_path, device, cand)['status'] == 'completed_with_unverified'
    assert device.calls == [('activate', 'aliases')]


def test_recovery_actual_before_state_and_created_inverse(tmp_path):
    device = Appliance(aliases=[alias('A', ['198.51.100.0/24'])])
    cand = candidate(device, documents(aliases=[alias(), alias('B')]))
    assert execute(tmp_path, device, cand)['status'] == 'completed_with_unverified'
    recovery = json.loads((tmp_path / 'recovery.json').read_text())
    req = {'schema_version': 1, 'selection': {'aliases': 'all'}}
    reverse = reverse_documents(recovery, req, device.read(['aliases']), TARGET)
    records = reverse['aliases'][TOP_LEVEL['aliases']]
    assert records[0]['content'] == ['198.51.100.0/24']
    assert records[1]['state'] == 'absent'
    device.resources['aliases'][0]['content'] = ['203.0.113.0/24']
    with pytest.raises(ValidationError, match='later'):
        reverse_documents(recovery, req, device.read(['aliases']), TARGET)


def test_private_output_failure_prevents_write(tmp_path, monkeypatch):
    import iaas_automation.opnsense_workflow.executor as module
    device = Appliance()
    cand = candidate(device, documents(aliases=[alias()]))
    original = module.save

    def fail_recovery(path, value):
        if path.name == 'recovery.json':
            raise OSError('synthetic unavailable output')
        return original(path, value)

    monkeypatch.setattr(module, 'save', fail_recovery)
    assert execute(tmp_path, device, cand)['status'] == 'failed'
    assert not device.calls


def test_external_reference_change_after_save_stops_before_activation(tmp_path):
    device = Appliance(aliases=[alias('A')])
    cand = candidate(device, documents(aliases=[alias('A', ['198.51.100.0/24'])]))
    original = device.save

    def external_edit(resource, records):
        result = original(resource, records)
        device.resources['filter-rules'] = [rule()]
        return result

    device.save = external_edit
    assert execute(tmp_path, device, cand)['status'] == 'failed'
    assert device.calls == [('save', 'aliases')]


def test_missing_read_coverage_cannot_overwrite_occupied_identity(tmp_path):
    cand = candidate(Appliance(), documents(aliases=[alias()]))
    cand['coverage'] = []
    device = Appliance(aliases=[alias(content=['203.0.113.0/24'])])
    result = execute(tmp_path, device, cand)
    assert result['status'] == 'failed'
    assert not device.calls
    assert device.resources['aliases'][0]['content'] == ['203.0.113.0/24']
    assert not (tmp_path / 'recovery.json').exists()


@pytest.mark.parametrize('remove', [False, True])
def test_rule_reference_removal_keeps_original_dependency_in_drift_scope(tmp_path, remove):
    device = Appliance(aliases=[alias('A'), alias('B')], filter_rules=[rule('A')])
    desired = rule('A', state='absent') if remove else rule('B')
    cand = candidate(device, documents(filter_rules=[desired]))
    result = execute(tmp_path, device, cand)
    assert result['status'] == 'completed_with_unverified'
    assert device.calls == [('save', 'filter-rules'), ('activate', 'filter-rules')]
    assert device.resources['aliases'] == [alias('A'), alias('B')]


def test_old_dependency_drift_after_reference_switch_still_stops_activation(tmp_path):
    device = Appliance(aliases=[alias('A'), alias('B')], filter_rules=[rule('A')])
    cand = candidate(device, documents(filter_rules=[rule('B')]))
    original = device.save

    def external_edit(resource, records):
        result = original(resource, records)
        device.resources['aliases'][0]['content'] = ['203.0.113.0/24']
        return result

    device.save = external_edit
    assert execute(tmp_path, device, cand)['status'] == 'failed'
    assert device.calls == [('save', 'filter-rules')]


def test_disabled_alias_old_table_cannot_confirm_activation(tmp_path):
    from iaas_automation.opnsense_workflow.reader import FixedCollectionTransport

    class OldTable(FixedCollectionTransport):
        def __init__(self):
            pass

        def _request(self, *args, **kwargs):
            return {'rows': [{'ip': '192.0.2.0/24'}], 'total': 1}

    device = Appliance(aliases=[alias()])
    device.activation = 'unconfirmed'
    device.active_check = OldTable().active_check
    cand = candidate(device, documents(aliases=[alias(enabled=False)]))
    result = execute(tmp_path, device, cand)
    assert result['status'] == 'failed'
    assert result['stages'][0]['configuration'] == 'verified'
    assert result['stages'][0]['activation'] == 'unconfirmed'


def test_recovery_unknown_and_manual_required_refused(tmp_path):
    device = Appliance()
    cand = candidate(device, documents(aliases=[alias()]))
    execute(tmp_path, device, cand)
    original = json.loads((tmp_path / 'recovery.json').read_text())
    req = {'selection': {'aliases': 'all'}}
    for field, value in [('after_status', 'unknown'), ('recovery', 'manual_required')]:
        recovery = deepcopy(original)
        recovery['entries'][0][field] = value
        with pytest.raises(ValidationError, match='reconciled|manual'):
            reverse_documents(recovery, req, device.read(['aliases']), TARGET)


def test_check_mode_has_no_provider_side_effect(tmp_path):
    device = Appliance()
    cand = candidate(device, documents(aliases=[alias()]))
    result = apply(cand, 'a' * 64, device, device, 'execution-1', {
        'target': TARGET, 'candidate_sha256': 'a' * 64, 'execution_id': 'execution-1',
        'checked_no_pending': True, 'serialized': True}, tmp_path, check_mode=True)
    assert result['status'] == 'checked' and not device.calls


def test_live_unselected_alias_type_is_checked():
    device = Appliance(aliases=[alias('PORTS', ['443'], type='port')])
    with pytest.raises(ValidationError, match='incompatible'):
        candidate(device, documents(filter_rules=[rule('PORTS')]))


@pytest.mark.parametrize('members', [['192.0.2.0/24'], ['2001:db8::/32'], ['192.0.2.0/24', '2001:db8::/32']])
def test_alias_address_families_are_preserved(members):
    cand = candidate(Appliance(), documents(aliases=[alias(content=members)]))
    assert cand['differences'][0]['after']['content'] == members
