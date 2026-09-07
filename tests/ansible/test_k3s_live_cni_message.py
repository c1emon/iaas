import pytest
import yaml
import json

from test_k3s_first_boot import ANSIBLE, run_tasks
from test_k3s_verify import PLAYBOOK, _extra, _inventory, _probe_outputs, _run


@pytest.mark.parametrize('suffix,expected', [('', True), (', container runtime is down', False)])
def test_current_k3s_cni_message_is_exactly_matched(tmp_path, suffix, expected):
    tasks = yaml.safe_load((ANSIBLE / 'roles/k3s_verify/tasks/verify-node.yml').read_text())
    task = next(t for t in tasks if t['name'].startswith('Record node readiness'))
    message = ('container runtime network not ready: NetworkReady=false '
               'reason:NetworkPluginNotReady message:Network plugin returns error: '
               'cni plugin not initialized' + suffix)
    result = run_tasks(tmp_path, [
        {'ansible.builtin.assert': {'that': ['(message | lower is match(pattern)) == expected']}}
    ], {'pattern': task['vars']['k3s_verify_cni_message_pattern'],
        'message': message, 'expected': expected})
    assert result.returncode == 0, result.stdout + result.stderr


def test_etcd_voter_is_not_a_pressure_condition(tmp_path):
    outputs = _probe_outputs(ready=False, reason='KubeletNotReady',
                             message='cni plugin not initialized')
    nodes = json.loads(outputs['nodes']['stdout'])
    nodes['items'][0]['status']['conditions'].append({
        'type': 'EtcdIsVoter', 'status': 'True', 'reason': 'MemberNotLearner'})
    outputs['nodes']['stdout'] = json.dumps(nodes)
    result = _run(['-i', str(_inventory(tmp_path, outputs=outputs)), str(PLAYBOOK), *_extra()])
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'WARN verify.synthetic-server-01.readiness' in result.stdout
