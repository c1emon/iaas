"""Representative v2 admission/content contracts using a synthetic adapter."""
from copy import deepcopy

import pytest

from iaas_automation.common.errors import ValidationError
from iaas_automation.opnsense_workflow.confirmation import action_results
from iaas_automation.opnsense_workflow.contracts import load_candidate, save
from test_opnsense_workflow import Appliance, alias, candidate, documents, execute, rule


class CapabilityAppliance(Appliance):
    missing = None

    def read(self, resources):
        observations = super().read(resources)
        if self.missing in observations:
            observations[self.missing]['confirmation_capability']['activation_completion'] = 'unsupported'
        return observations


def test_last_stage_gap_blocks_every_write(tmp_path):
    device = CapabilityAppliance()
    cand = candidate(device, documents(aliases=[alias()], filter_rules=[rule()]))
    assert cand['admission']['status'] == 'ready'
    device.missing = 'filter-rules'
    assert execute(tmp_path, device, cand)['status'] == 'failed'
    assert device.calls == []
    blocked = candidate(device, documents(aliases=[alias()], filter_rules=[rule()]))
    assert blocked['admission']['status'] == 'blocked'
    path = tmp_path / 'candidate.json'
    digest = save(path, blocked)
    assert load_candidate(path, digest)[0]['admission']['status'] == 'blocked'
    device.missing = None
    assert execute(tmp_path, device, blocked)['status'] == 'failed'
    assert device.calls == []


def test_noop_needs_no_action_capability():
    device = CapabilityAppliance(aliases=[alias()])
    device.missing = 'aliases'
    cand = candidate(device, documents(aliases=[alias()]))
    assert cand['stages'] == [] and cand['admission']['status'] == 'ready'


def dynamic(**extra):
    return alias(**{'type': 'urltable', 'content': ['https://example.org/a.txt'], 'updatefreq_days': '1', **extra})


@pytest.mark.parametrize('before,after,trigger,action', [
    (None, dynamic(), 'created', 'initialize'),
    (dynamic(enabled=False), dynamic(), 're_enabled', 'update'),
    (dynamic(), dynamic(content=['https://example.org/b.txt']), 'source_changed', 'update'),
])
def test_content_transitions_are_bound_and_do_not_permit_unproven_cache(tmp_path, before, after, trigger, action):
    device = Appliance(aliases=[before] if before else [])
    cand = candidate(device, documents(aliases=[after]))
    content = cand['stages'][0]['content_actions'][0]
    assert (content['trigger'], content['action']) == (trigger, action)
    assert content['cache']['reuse'] is False
    assert content['execution'] == 'native_activation'
    path = tmp_path / 'candidate.json'
    reviewed = save(path, cand)
    cand['stages'][0]['content_actions'][0]['cache']['reuse'] = True
    save(path, cand)
    with pytest.raises(ValidationError, match='digest'):
        load_candidate(path, reviewed)
    with pytest.raises(ValidationError, match='confirmation'):
        load_candidate(path)


def test_description_and_retirement_do_not_force_refresh():
    device = Appliance(aliases=[dynamic()])
    for after in (dynamic(description='changed'), dynamic(enabled=False), dynamic(state='absent')):
        cand = candidate(device, documents(aliases=[after]))
        assert cand['stages'][0]['content_actions'] == []


def test_recovery_gap_has_manual_exit_without_fabricated_difference():
    device = CapabilityAppliance(aliases=[dynamic()])
    device.missing = 'aliases'
    cand = candidate(device, documents(aliases=[dynamic()]), activation_recovery={'aliases': [['A']]})
    assert cand['differences'][0]['action'] == 'unchanged'
    assert cand['admission']['status'] == 'blocked'
    assert cand['admission']['recovery'] == 'manual_required'
    assert 'configuration reversal' in cand['admission']['guidance']
    assert cand['stages'][0]['content_actions'][0]['execution'] == 'native_activation'


@pytest.mark.parametrize('status,expected', [('confirmed', 'completed_with_unverified'), ('failed', 'failed')])
def test_equal_members_do_not_decide_content_processing(tmp_path, status, expected):
    device = Appliance(aliases=[dynamic()])
    after = dynamic(content=['https://example.org/b.txt'])
    cand = candidate(device, documents(aliases=[after]))
    content = cand['stages'][0]['content_actions'][0]
    device.active_check = lambda *args: {'status': 'verified'}

    def activate(resource):
        device.calls.append(('activate', resource))
        return {'status': 'confirmed', 'content_update': [
            {'identity': ['A'], 'source': content['source'], 'status': status, 'loading': 'confirmed'}]}

    device.activate = activate
    result = execute(tmp_path, device, cand)
    assert result['status'] == ('fully_verified' if status == 'confirmed' else expected)
    assert result['stages'][0]['content_update'][0]['status'] == status
    assert result['stages'][0]['active'][0]['active']['status'] == 'verified'
    assert device.calls == [('save', 'aliases'), ('activate', 'aliases')]


def test_one_content_success_does_not_cover_another_identity():
    device = Appliance()
    cand = candidate(device, documents(aliases=[dynamic(), dynamic(name='B')]))
    stage = cand['stages'][0]
    action = stage['content_actions'][0]
    rows = action_results(stage, {'content_update': [
        {'identity': ['A'], 'source': action['source'], 'status': 'confirmed', 'loading': 'confirmed'}]})
    assert [row['status'] for row in rows] == ['confirmed', 'unknown']


@pytest.mark.parametrize('response,expected', [
    ({'product': {'product_version': '26.7.3'}}, 'available'),
    ({'product': {'product_version': '26.1.11'}}, 'unknown'),
    ({}, 'unknown'),
])
def test_fixed_version_qualified_capabilities(response, expected):
    from iaas_automation.opnsense_workflow.reader import FixedCollectionTransport

    class Wire(FixedCollectionTransport):
        def __init__(self):
            self.calls = []

        def _request(self, method, path, payload=None):
            self.calls.append((method, path))
            return response

    wire = Wire()
    caps = wire.confirmation_capabilities()
    assert caps['filter-rules']['activation_completion'] == expected
    assert caps['vips']['activation_completion'] == expected
    assert caps['aliases']['activation_completion'] != 'available'
    assert caps['gateways']['activation_completion'] != 'available'
    assert caps['interface-groups']['activation_completion'] != 'available'
    assert wire.calls == [('GET', 'core/firmware/status')]


def test_fixed_capability_gaps_cannot_be_overridden_by_controller_ok(tmp_path):
    device = CapabilityAppliance()
    device.missing = 'aliases'
    cand = candidate(device, documents(aliases=[alias()]))
    device.activation = 'confirmed'
    result = execute(tmp_path, device, cand)
    assert result['status'] == 'failed'
    assert not device.calls


def test_correlated_wait_is_read_only_and_stops_on_conflict():
    from iaas_automation.opnsense_workflow.confirmation import complete_action
    device = Appliance()
    stage = candidate(device, documents(aliases=[alias()]))['stages'][0]
    observed = []

    def observe(stage, action_id, *, timeout):
        observed.append(timeout)
        return {'status': 'confirmed', 'action_id': action_id, 'complete': True, 'fresh': True}

    device.observe_confirmation = observe
    result = complete_action(stage, {'status': 'processing', 'action_id': 'native-1'}, device, lambda: None)
    assert result['status'] == 'confirmed' and len(observed) == 1
    assert device.calls == []

    def conflict():
        raise ValidationError('unrelated pending activation conflict')

    result = complete_action(stage, {'status': 'processing', 'action_id': 'native-1'}, device, conflict)
    assert result['status'] == 'unknown' and len(observed) == 1
    assert device.calls == []
