"""Execute controller-only scope selection; never run deployment roles."""
import os
from pathlib import Path
import shlex
import subprocess

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
MODEL = ROOT / 'tests/fixtures/k3s/expected-review.yml'


@pytest.mark.parametrize('target', ['k3s-preflight', 'k3s-verify', 'k3s-deploy'])
def test_make_keeps_controller_in_execution_limit(target):
    result = subprocess.run(
        ['make', '-n', target, 'K3S_INTENT=intent.yml', 'K3S_INVENTORY=inventory.yml',
         'K3S_SCOPE=node-a,node-b', 'K3S_RUNTIME_SECRETS=unused.json'],
        cwd=ROOT, capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0, result.stderr
    command = next(line for line in result.stdout.splitlines() if 'ansible-playbook -i' in line)
    args = shlex.split(command)
    assert args[args.index('-l') + 1] == 'localhost,node-a,node-b'
    assert f'k3s_{"deploy" if target == "k3s-deploy" else "preflight" if target == "k3s-preflight" else "verify"}_scope=node-a,node-b' in args


@pytest.mark.parametrize('case', ['string', 'list', 'missing', 'duplicate', 'unknown'])
def test_controller_scope_executes_without_remote_actions(tmp_path, case):
    model = yaml.safe_load(MODEL.read_text())
    names = [node['vm_ref'] for node in model['nodes']]
    scope = names if case == 'list' else ','.join(names)
    if case == 'missing':
        scope = ','.join(names[:-1])
    elif case == 'duplicate':
        scope += ',' + names[0]
    elif case == 'unknown':
        scope += ',unknown-node'
    source = yaml.safe_load((ROOT / 'automation/ansible/playbooks/k3s/deploy.yml').read_text())
    play = source[1]
    play['connection'] = 'local'
    play['vars'].update(k3s_deploy_model_path=str(MODEL), k3s_deploy_scope=scope,
                        k3s_deploy_runtime_secret_file='unused-no-secret-read')
    # Only localhost assertions and in-memory add_host; no remote play is copied.
    path = tmp_path / 'controller.yml'
    path.write_text(yaml.safe_dump([play]))
    environment = dict(os.environ, ANSIBLE_CONFIG=str(ROOT / 'automation/ansible/ansible.cfg'))
    result = subprocess.run(['uv', 'run', 'ansible-playbook', '-i', 'localhost,',
                             '-l', 'localhost,' + ','.join(names), str(path)],
                            cwd=ROOT, env=environment, capture_output=True, text=True, check=False)
    assert (result.returncode == 0) == (case in ['string', 'list']), result.stdout + result.stderr
    if result.returncode == 0:
        assert 'Materialize ordered deployment groups' in result.stdout
        assert 'skipping: no hosts matched' not in result.stdout
