"""Representative v2 admission/content contracts using a synthetic adapter."""
from copy import deepcopy

import pytest

from iaas.common.errors import ValidationError
from iaas.opnsense_workflow.confirmation import action_results
from iaas.opnsense_workflow.contracts import load_candidate, save
from iaas.opnsense_workflow.executor import verify
from test_opnsense_workflow import Appliance, alias, candidate, documents, execute, rule


class CapabilityAppliance(Appliance):
    missing = None

    def read(self, resources):
        observations = super().read(resources)
        if self.missing in observations:
            observations[self.missing].pop('confirmation_capability', None)
        return observations

    def confirmation_capabilities(self):
        raise AssertionError('firmware capability probing is optional')


def test_missing_capability_and_unreadable_firmware_do_not_block_write(tmp_path):
    device = CapabilityAppliance()
    cand = candidate(device, documents(aliases=[alias()], filter_rules=[rule()]))
    assert cand['admission']['status'] == 'ready'
    device.missing = 'filter-rules'
    result = execute(tmp_path, device, cand)
    assert result['status'] == 'fully_verified'
    assert device.calls == [('save', 'aliases'), ('activate', 'aliases'),
                             ('save', 'filter-rules'), ('activate', 'filter-rules')]
    ready = candidate(device, documents(aliases=[alias()], filter_rules=[rule()]))
    assert ready['admission']['status'] == 'ready'
    path = tmp_path / 'candidate.json'
    digest = save(path, ready)
    assert load_candidate(path, digest)[0]['admission']['status'] == 'ready'


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
def test_content_transitions_bind_provider_native_cache_policy(tmp_path, before, after, trigger, action):
    device = Appliance(aliases=[before] if before else [])
    cand = candidate(device, documents(aliases=[after]))
    content = cand['stages'][0]['content_actions'][0]
    assert (content['trigger'], content['action']) == (trigger, action)
    assert content['cache'] == {'policy': 'provider_native'}
    assert content['execution'] == 'native_activation'
    path = tmp_path / 'candidate.json'
    reviewed = save(path, cand)
    cand['stages'][0]['content_actions'][0]['cache']['policy'] = 'unreviewed'
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
    assert cand['admission']['status'] == 'ready'
    assert cand['admission']['recovery'] == 'not_required'
    assert cand['stages'][0]['content_actions'][0]['execution'] == 'native_activation'


@pytest.mark.parametrize('status,expected', [('confirmed', 'fully_verified'), ('failed', 'failed')])
def test_equal_members_do_not_decide_content_processing(tmp_path, status, expected):
    device = Appliance(aliases=[dynamic()])
    after = dynamic(content=['https://example.org/b.txt'])
    cand = candidate(device, documents(aliases=[after]))
    content = cand['stages'][0]['content_actions'][0]
    device.active_check = lambda *args: (_ for _ in ()).throw(AssertionError('optional active check'))

    def activate(resource):
        device.calls.append(('activate', resource))
        return {'status': 'confirmed', 'content_update': [
            {'identity': ['A'], 'source': content['source'], 'status': status, 'loading': 'confirmed'}]}

    device.activate = activate
    result = execute(tmp_path, device, cand)
    assert result['status'] == ('fully_verified' if status == 'confirmed' else expected)
    assert result['stages'][0]['content_update'][0]['status'] == ('provider_managed' if status == 'confirmed' else 'failed')
    assert result['stages'][0]['active'][0]['active']['status'] == 'not_attempted'
    assert device.calls == [('save', 'aliases'), ('activate', 'aliases')]


def test_explicit_content_failure_stops_static_alias_stage(tmp_path):
    device = Appliance()
    cand = candidate(device, documents(aliases=[alias()]))
    assert cand['stages'][0]['content_actions'] == []

    def activate(resource):
        device.calls.append(('activate', resource))
        return {'status': 'confirmed', 'content_update': [
            {'identity': ['A'], 'status': 'failed'}]}

    device.activate = activate
    result = execute(tmp_path, device, cand)
    assert result['status'] == 'failed'
    assert result['stages'][0]['activation'] == 'confirmed'
    assert device.calls == [('save', 'aliases'), ('activate', 'aliases')]


def test_one_content_success_does_not_cover_another_identity():
    device = Appliance()
    cand = candidate(device, documents(aliases=[dynamic(), dynamic(name='B')]))
    stage = cand['stages'][0]
    action = stage['content_actions'][0]
    rows = action_results(stage, {'content_update': [
        {'identity': ['A'], 'source': action['source'], 'status': 'confirmed', 'loading': 'confirmed'}]})
    assert [row['status'] for row in rows] == ['confirmed', 'unknown']


def test_default_verify_ignores_optional_active_check(tmp_path):
    device = CapabilityAppliance()
    device.missing = 'aliases'
    cand = candidate(device, documents(aliases=[alias()]))
    device.active_check = lambda *args: (_ for _ in ()).throw(AssertionError('optional active check'))
    result = execute(tmp_path, device, cand)
    assert result['status'] == 'fully_verified'
    checks = verify(cand, device)
    assert checks['status'] == 'fully_verified'
    assert checks['scope'] == 'saved_configuration'
    assert checks['objects'][0]['active']['status'] == 'not_attempted'


def test_native_limitation_warning_is_recorded_once_without_source_or_credentials(tmp_path, capsys):
    source = 'https://secret.invalid/source.txt'
    device = Appliance()
    cand = candidate(device, documents(aliases=[dynamic(content=[source])]))

    result = execute(tmp_path, device, cand)
    warning_code = 'IAAS-OPNSENSE-RESULT-LIMITATION'
    assert len(result['warnings']) == 1
    assert result['stages'][0]['warnings'] == result['warnings']
    stderr = capsys.readouterr().err
    assert stderr.count(warning_code) == 1
    assert source not in stderr
    assert 'OPNSENSE_API' not in stderr


def test_correlated_wait_is_read_only_and_stops_on_conflict():
    from iaas.opnsense_workflow.confirmation import complete_action
    from iaas.opnsense_workflow.confirmation import WAIT_POLICY
    device = Appliance()
    stage = candidate(device, documents(aliases=[alias()]))['stages'][0]
    stage['confirmation']['wait'] = deepcopy(WAIT_POLICY)
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
