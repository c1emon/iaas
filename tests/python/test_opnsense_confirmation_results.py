"""Current-state verification must not certify an earlier action."""
import pytest

from iaas_automation.opnsense_workflow.executor import verify
from test_opnsense_workflow import Appliance, alias, candidate, documents, execute


@pytest.mark.parametrize('activation', ['accepted', 'unconfirmed', 'failed'])
def test_matching_members_never_promote_activation(tmp_path, activation):
    device = Appliance()
    device.activation = activation
    device.active_check = lambda *args: (_ for _ in ()).throw(AssertionError('optional active check'))
    cand = candidate(device, documents(aliases=[alias()]))
    result = execute(tmp_path, device, cand)
    assert result['status'] == 'failed'
    assert result['stages'][0]['activation'] == activation
    assert result['stages'][0]['active'][0]['active']['status'] == 'not_attempted'
    before = (tmp_path / 'result.json').read_bytes()
    checks = verify(cand, device)
    assert checks['status'] == 'fully_verified'
    assert checks['scope'] == 'saved_configuration'
    assert checks['historical_actions']['activation'] == 'not_provided'
    assert (tmp_path / 'result.json').read_bytes() == before
    assert len(device.calls) == 2


@pytest.mark.parametrize('active', [
    {'status': 'unsupported'},
    {'status': 'unsupported', 'required': True},
    {'status': 'not_applicable', 'reason': 'complete_native_consumer_observation_empty'},
    {'status': 'not_applicable'},
    {'status': 'unknown'},
    {'status': 'incomplete'},
    {'status': 'failed'},
])
def test_saved_configuration_verify_ignores_optional_active_state(active):
    device = Appliance(aliases=[alias()])
    device.active_check = lambda *args: active
    cand = candidate(device, documents(aliases=[alias()]))
    result = verify(cand, device)
    assert result['status'] == 'fully_verified'
    assert result['scope'] == 'saved_configuration'
    assert result['objects'][0]['active']['status'] == 'not_attempted'
    assert device.calls == []
