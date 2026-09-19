"""Current-state verification must not certify an earlier action."""
import pytest

from iaas_automation.opnsense_workflow.executor import verify
from test_opnsense_workflow import Appliance, alias, candidate, documents, execute


@pytest.mark.parametrize('activation', ['accepted', 'unconfirmed', 'failed'])
def test_matching_members_never_promote_activation(tmp_path, activation):
    device = Appliance()
    device.activation = activation
    device.active_check = lambda *args: {'status': 'verified'}
    cand = candidate(device, documents(aliases=[alias()]))
    result = execute(tmp_path, device, cand)
    assert result['status'] == 'failed'
    assert result['stages'][0]['activation'] == activation
    assert result['stages'][0]['active'][0]['active']['status'] == 'verified'
    before = (tmp_path / 'result.json').read_bytes()
    checks = verify(cand, device)
    assert checks['status'] == 'fully_verified'
    assert checks['scope'] == 'current_state'
    assert checks['historical_actions']['activation'] == 'not_provided'
    assert (tmp_path / 'result.json').read_bytes() == before
    assert len(device.calls) == 2


@pytest.mark.parametrize('active,status', [
    ({'status': 'unsupported'}, 'completed_with_unverified'),
    ({'status': 'unsupported', 'required': True}, 'failed'),
    ({'status': 'not_applicable', 'reason': 'complete_native_consumer_observation_empty'}, 'fully_verified'),
    ({'status': 'not_applicable'}, 'failed'),
    ({'status': 'unknown'}, 'failed'),
    ({'status': 'incomplete'}, 'failed'),
    ({'status': 'failed'}, 'failed'),
])
def test_current_state_aggregation(active, status):
    device = Appliance(aliases=[alias()])
    device.active_check = lambda *args: active
    cand = candidate(device, documents(aliases=[alias()]))
    assert verify(cand, device)['status'] == status
    assert device.calls == []
