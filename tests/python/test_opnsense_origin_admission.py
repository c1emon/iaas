"""Representative classification gates across planning, execution and recovery."""
from copy import deepcopy
import json

import pytest

from iaas.common.errors import ValidationError
from iaas.opnsense_workflow.contracts import key, load_candidate, save
from iaas.opnsense_workflow.executor import reverse_documents
from iaas.opnsense_workflow.planning import plan
from test_opnsense_workflow import (Appliance, RUNTIME, TARGET, alias, candidate,
                                    documents, execute, rule)


def classification(management='independent', origin='user_config', **extra):
    return {'origin': origin, 'management': management, 'basis': ['supported_model'], **extra}


class ClassifiedAppliance(Appliance):
    def __init__(self, *, management='independent', origin='user_config', native=None, **resources):
        super().__init__(**resources)
        self.classification = classification(management, origin)
        self.native = native or {}

    def read(self, resources):
        observations = super().read(resources)
        for resource, observation in observations.items():
            observation['observation_scope'] = 'configuration'
            for obj in observation['objects']:
                obj['classification'] = deepcopy(self.classification)
            observation['objects'].extend(deepcopy(self.native.get(resource, [])))
        return observations


def system_reference(resource='aliases', name='SYSTEM_NET', role='address', **support):
    return {'identity': [name], 'configuration': None, 'recovery': 'manual_required',
            'references': [], 'classification': classification('read_only', 'system_builtin'),
            'reference_support': {'label': resource + ':' + name, 'roles': [role],
                                  'basis': ['reference_role_from_native_identity'], 'dependencies_complete': True,
                                  **({'ip_protocol': 'inet46'} if role == 'address' else {}),
                                  **support}}


@pytest.mark.parametrize('management', ['read_only', 'via_source', 'unknown'])
@pytest.mark.parametrize('operation', ['update', 'delete', 'activation_recovery'])
def test_non_independent_target_never_gains_write_rights(management, operation):
    device = ClassifiedAppliance(management=management, aliases=[alias()])
    desired = alias(content=['203.0.113.0/24']) if operation == 'update' else alias()
    options = {}
    if operation == 'delete':
        desired['state'] = 'absent'
    if operation == 'activation_recovery':
        options['activation_recovery'] = {'aliases': [['A']]}
    with pytest.raises(ValidationError, match='managed|management|read-only'):
        candidate(device, documents(aliases=[desired]), **options)
    assert device.calls == []


def test_activation_recovery_requires_existing_identity():
    with pytest.raises(ValidationError, match='existing observed identity'):
        candidate(ClassifiedAppliance(), documents(aliases=[alias(state='absent')]),
                  activation_recovery={'aliases': [['A']]})


def test_uncontrolled_classification_basis_is_rejected():
    device = ClassifiedAppliance(aliases=[alias()])
    device.classification['basis'] = ['raw_provider_response']
    with pytest.raises(ValidationError, match='invalid resource classification'):
        candidate(device, documents(aliases=[alias()]))


def test_source_managed_error_includes_known_source():
    device = ClassifiedAppliance(management='via_source', aliases=[alias()])
    device.classification['source'] = 'firewall/group/static-child'
    with pytest.raises(ValidationError, match='firewall/group/static-child'):
        candidate(device, documents(aliases=[alias(content=['203.0.113.0/24'])]))


def test_system_address_and_group_dependencies_need_no_fake_configuration(tmp_path):
    device = ClassifiedAppliance(native={
        'aliases': [system_reference()],
        'interface-groups': [system_reference('interface-groups', 'vpn_group', 'interface-group')],
    })
    cand = candidate(device, documents(filter_rules=[rule('SYSTEM_NET', interface=['vpn_group'])]))
    assert cand['before'][key('aliases', ['SYSTEM_NET'])]['configuration'] is None
    assert execute(tmp_path, device, cand)['status'] == 'fully_verified'
    assert all(resource == 'filter-rules' for _, resource in device.calls)


@pytest.mark.parametrize('support', [
    {'roles': ['port']}, {'dependencies_complete': False}, {'basis': []},
    {'ip_protocol': 'inet6'}, {'ip_protocol': None},
])
def test_system_reference_cannot_bypass_role_or_evidence(support):
    obj = system_reference(**support)
    device = ClassifiedAppliance(native={'aliases': [obj]})
    with pytest.raises(ValidationError, match='reference|dependency|family'):
        candidate(device, documents(filter_rules=[rule('SYSTEM_NET')]))


def test_address_alias_is_not_a_port_alias():
    device = ClassifiedAppliance(native={'aliases': [system_reference()]})
    with pytest.raises(ValidationError, match='reference'):
        candidate(device, documents(filter_rules=[rule('192.0.2.0/24', destination_port='SYSTEM_NET')]))


def test_unknown_origin_does_not_gain_system_reference_exception():
    obj = system_reference()
    obj['classification']['origin'] = 'unknown'
    with pytest.raises(ValidationError, match='system origin'):
        candidate(ClassifiedAppliance(native={'aliases': [obj]}),
                  documents(filter_rules=[rule('SYSTEM_NET')]))


def test_interface_choice_does_not_override_observed_reference_evidence():
    obj = system_reference('interface-groups', 'lan', 'interface-group', dependencies_complete=False)
    with pytest.raises(ValidationError, match='dependency'):
        candidate(ClassifiedAppliance(native={'interface-groups': [obj]}),
                  documents(filter_rules=[rule('192.0.2.0/24')]))


def test_native_reverse_reference_still_blocks_delete():
    obj = system_reference()
    obj['references'] = ['aliases:A']
    device = ClassifiedAppliance(aliases=[alias()], native={'aliases': [obj]})
    with pytest.raises(ValidationError, match='missing dependency'):
        candidate(device, documents(aliases=[alias(state='absent')]))


def test_system_transitive_dependency_is_not_assumed_empty():
    obj = system_reference()
    obj['references'] = ['aliases:MISSING']
    with pytest.raises(ValidationError, match='missing dependency'):
        candidate(ClassifiedAppliance(native={'aliases': [obj]}),
                  documents(filter_rules=[rule('SYSTEM_NET')]))


def test_unrelated_unknown_does_not_block_user_change(tmp_path):
    unknown = {'identity': ['UNKNOWN'], 'configuration': None, 'references': [],
               'classification': classification('unknown', 'unknown'), 'recovery': 'manual_required'}
    device = ClassifiedAppliance(native={'aliases': [unknown]})
    cand = candidate(device, documents(aliases=[alias()]))
    assert execute(tmp_path, device, cand)['status'] == 'fully_verified'


@pytest.mark.parametrize('field,value', [('management', 'read_only'), ('source', 'different_source'),
                                        ('basis', ['different_evidence'])])
def test_management_drift_stops_before_save(tmp_path, field, value):
    device = ClassifiedAppliance(aliases=[alias()])
    cand = candidate(device, documents(aliases=[alias(content=['203.0.113.0/24'])]))
    device.classification[field] = value
    assert execute(tmp_path, device, cand)['status'] == 'failed'
    assert device.calls == []


def test_origin_label_correction_alone_does_not_block(tmp_path):
    device = ClassifiedAppliance(aliases=[alias()])
    cand = candidate(device, documents(aliases=[alias(content=['203.0.113.0/24'])]))
    device.classification['origin'] = 'derived'
    assert execute(tmp_path, device, cand)['status'] == 'fully_verified'


def test_reference_role_drift_stops_before_save(tmp_path):
    device = ClassifiedAppliance(native={'aliases': [system_reference()]})
    cand = candidate(device, documents(filter_rules=[rule('SYSTEM_NET')]))
    device.native['aliases'][0]['reference_support']['roles'] = ['port']
    assert execute(tmp_path, device, cand)['status'] == 'failed'
    assert device.calls == []


def test_created_object_needs_actual_management_evidence(tmp_path):
    class LostEvidence(ClassifiedAppliance):
        def save(self, resource, records):
            result = super().save(resource, records)
            self.classification['management'] = 'unknown'
            return result

    device = LostEvidence()
    cand = candidate(device, documents(aliases=[alias()]))
    assert execute(tmp_path, device, cand)['status'] == 'failed'
    assert device.calls == [('save', 'aliases')]


@pytest.mark.parametrize('legacy', [1, 2])
def test_old_candidates_need_replanning(tmp_path, legacy):
    cand = candidate(ClassifiedAppliance(), documents(aliases=[alias()]))
    cand['schema_version'] = legacy
    path = tmp_path / 'candidate.json'
    save(path, cand)
    with pytest.raises(ValidationError, match='re-plan'):
        load_candidate(path)


def test_v3_missing_classification_is_not_upgraded(tmp_path):
    cand = candidate(ClassifiedAppliance(aliases=[alias()]), documents(aliases=[alias()]))
    del cand['before'][key('aliases', ['A'])]['classification']
    path = tmp_path / 'candidate.json'
    save(path, cand)
    with pytest.raises(ValidationError, match='classification'):
        load_candidate(path)


def test_display_projection_is_not_execution_state():
    device = ClassifiedAppliance()
    observed = device.read(['aliases', 'filter-rules', 'dnat', 'one-to-one-nat', 'gateways', 'interface-groups'])
    observed['aliases']['observation_scope'] = 'display'
    with pytest.raises(ValidationError, match='display view'):
        plan(documents(aliases=[alias()]), {'schema_version': 1, 'selection': {'aliases': 'all'}},
             observed, TARGET, RUNTIME, {})


def test_deleted_user_object_can_be_recreated_but_not_overwrite_a_new_occupant(tmp_path):
    device = ClassifiedAppliance(aliases=[alias()])
    cand = candidate(device, documents(aliases=[alias(state='absent')]))
    assert execute(tmp_path / 'delete', device, cand)['status'] == 'fully_verified'
    recovery = json.loads((tmp_path / 'delete/recovery.json').read_text())
    req = {'schema_version': 1, 'selection': {'aliases': [['A']]}}
    restored = reverse_documents(recovery, req, device.read(['aliases']), TARGET)
    recreated = candidate(device, restored)
    assert execute(tmp_path / 'recreate', device, recreated)['status'] == 'fully_verified'
    with pytest.raises(ValidationError, match='later .*change'):
        reverse_documents(recovery, req, device.read(['aliases']), TARGET)


def test_recovery_rejects_old_format_and_changed_management(tmp_path):
    device = ClassifiedAppliance()
    cand = candidate(device, documents(aliases=[alias()]))
    assert execute(tmp_path, device, cand)['status'] == 'fully_verified'
    recovery = json.loads((tmp_path / 'recovery.json').read_text())
    req = {'schema_version': 1, 'selection': {'aliases': [['A']]}}
    old = {**recovery, 'schema_version': 2}
    with pytest.raises(ValidationError, match='retain evidence'):
        reverse_documents(old, req, device.read(['aliases']), TARGET)
    device.classification['management'] = 'read_only'
    with pytest.raises(ValidationError, match='read-only'):
        reverse_documents(recovery, req, device.read(['aliases']), TARGET)
