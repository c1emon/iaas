"""Controller-local regressions; no VM, service or external endpoint access."""
import json
import base64
import os
from pathlib import Path
import subprocess

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
ANSIBLE = ROOT / 'automation/ansible'


def run_tasks(tmp_path, tasks, variables):
    play = tmp_path / 'local.yml'
    play.write_text(yaml.safe_dump([{'hosts': 'localhost', 'connection': 'local',
                                   'gather_facts': False, 'vars': variables, 'tasks': tasks}]))
    return subprocess.run(['uv', 'run', 'ansible-playbook', '-i', 'localhost,', str(play)],
                          cwd=ROOT, env=dict(os.environ, ANSIBLE_CONFIG=str(ANSIBLE / 'ansible.cfg')),
                          capture_output=True, text=True, check=False)


def test_live_probe_shape_and_null_credentials(tmp_path):
    source = yaml.safe_load((ANSIBLE / 'roles/k3s_preflight/tasks/main.yml').read_text())
    selected = [task for task in source if task['name'] in [
        'Build runtime facts from read-only probes',
        'Resolve credential and TLS reference sets without retaining secret values']]
    results = [{'rc': 0, 'stdout': value} for value in
               ['cgroup2fs', 'CapEff', 'yes', '10.10.0.20', '', '20000000000', '', '']]
    variables = {
        'k3s_preflight_node': {'vm_ref': 'localhost', 'node_ip': '10.10.0.20', 'node_nic': 'mgmt0'},
        'k3s_preflight_reachable': True,
        'pve_architecture': 'amd64',
        'k3s_preflight_setup': {'ansible_facts': {'ansible_os_family': 'Debian',
                              'ansible_distribution': 'Debian', 'ansible_architecture': 'x86_64'}},
        'k3s_preflight_probes': {'results': results},
        'k3s_preflight_port_checks': {'results': []},
        'k3s_preflight_artifact': {'credential_ref': None},
        'k3s_preflight_service_proxy': {'credential_ref': None},
        'k3s_preflight_registry_mirrors': [{'auth_ref': None}],
    }
    selected.append({'ansible.builtin.assert': {'that': [
        "k3s_preflight_runtime.os_family == 'Debian'",
        'k3s_preflight_runtime.free_bytes | int == 20000000000',
        'k3s_preflight_required_credential_refs == []']}})
    result = run_tasks(tmp_path, selected, variables)
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize('realm,valid', [('https://harbor.synthetic.invalid:883/service/token', True),
                                      ('https://other.invalid/token', False),
                                      ('http://harbor.synthetic.invalid:883/token', False)])
def test_bearer_challenge_authentication_gate(tmp_path, realm, valid):
    tasks = yaml.safe_load((ANSIBLE / 'roles/k3s_preflight/tasks/registry-bearer.yml').read_text())
    # Exercise the real challenge parsing and credential destination gate, without HTTP.
    result = run_tasks(tmp_path, tasks[:2], {'k3s_registry_challenge': {
        'www_authenticate': f'Bearer realm="{realm}",service="harbor-registry"',
        'item': {'endpoint': 'https://harbor.synthetic.invalid:883',
                 'auth_ref': 'op://synthetic/registry/credentials'}}})
    assert (result.returncode == 0) == valid, result.stdout + result.stderr


def test_service_units_load_proxy_environment():
    for role, service in [('k3s_server', 'k3s'), ('k3s_agent', 'k3s-agent')]:
        unit = (ANSIBLE / f'roles/{role}/templates/{service}.service.j2').read_text()
        assert f'EnvironmentFile=/etc/systemd/system/{service}.service.env' in unit
        assert 'Delegate=yes' in unit


@pytest.mark.parametrize('expected,active,valid', [
    ('synthetic-password', 'server:synthetic-password', True),
    ('synthetic-password', 'server:wrong', False),
    ('K10' + 'a' * 64 + '::server:p', 'server:p', True),
    ('K10' + 'b' * 64 + '::server:p', 'server:p', False),
])
def test_bootstrap_short_and_secure_token_comparison(tmp_path, expected, active, valid):
    source = yaml.safe_load((ANSIBLE / 'playbooks/k3s/deploy.yml').read_text())
    check = next(task for play in source for task in play.get('tasks', [])
                 if task.get('name') == 'Compare active secure-token credential and optional CA hash')
    secret = tmp_path / 'synthetic.json'
    secret.write_text(json.dumps({'op://synthetic/server/token': expected}))
    secret.chmod(0o600)
    setup = {'ansible.builtin.set_fact': {'k3s_deploy_active_token_read': {
        'content': base64.b64encode(('K10' + 'a' * 64 + '::' + active).encode()).decode()}}}
    result = run_tasks(tmp_path, [setup, check], {
        'k3s_deploy_bootstrap_vm_ref': 'localhost',
        'k3s_deploy_model': {'cluster': {'server_token_ref': 'op://synthetic/server/token'}},
        'k3s_deploy_runtime_secret_file': str(secret),
    })
    assert (result.returncode == 0) == valid, result.stdout + result.stderr


def test_apt_extraction_expression_matches_tsinghua_url(tmp_path):
    source = yaml.safe_load((ANSIBLE / 'roles/k3s_preflight/tasks/main.yml').read_text())
    probe = next(task for task in source if task['name'].startswith('Read configured APT source'))
    result = run_tasks(tmp_path, [{'ansible.builtin.assert': {'that': [
        "(" + probe['loop'][3:-3] + ") == ['https://mirrors.tuna.tsinghua.edu.cn/debian']"]}}],
        {'k3s_preflight_probes': {'results': [{}, {}, {}, {}, {}, {}, {
            'stdout': 'URIs: https://mirrors.tuna.tsinghua.edu.cn/debian\n'}]}})
    assert result.returncode == 0, result.stdout + result.stderr


def test_agent_config_omits_server_only_options(tmp_path):
    model = yaml.safe_load((ROOT / 'tests/fixtures/k3s/expected-review.yml').read_text())
    agent = next(node for node in model['nodes'] if node['role'] == 'agent')
    template = str(ANSIBLE / 'roles/k3s_runtime_config/templates/config.yaml.j2')
    result = run_tasks(tmp_path, [
        {'ansible.builtin.set_fact': {'rendered': "{{ lookup('template', template_path) | from_yaml }}"}},
        {'ansible.builtin.assert': {'that': [
            "rendered['node-name'] == k3s_runtime_node.vm_ref",
            "'server' in rendered", "'cluster-cidr' not in rendered",
            "'service-cidr' not in rendered", "'flannel-backend' not in rendered",
            "'disable' not in rendered", "'tls-san' not in rendered"]}},
    ], {'k3s_runtime_model': model, 'k3s_runtime_node': agent,
        'k3s_runtime_join_token': 'synthetic', 'template_path': template})
    assert result.returncode == 0, result.stdout + result.stderr


def test_bearer_exchange_templates_with_synthetic_responses(tmp_path):
    tasks = yaml.safe_load((ANSIBLE / 'roles/k3s_preflight/tasks/registry-bearer.yml').read_text())
    for task in tasks:
        if 'ansible.builtin.uri' not in task:
            continue
        request = task.pop('ansible.builtin.uri')
        task.pop('delegate_to')
        task.pop('register', None)
        if 'headers' in request:
            task['ansible.builtin.assert'] = {'that': [
                "(" + request['headers']['Authorization'].replace('Bearer ', '').strip()[3:-3] + ") == 'synthetic-token'"
            ]}
        else:
            task['ansible.builtin.set_fact'] = {'k3s_preflight_registry_token_response': {
                'json': {'token': 'synthetic-token'}}}
    tasks.append({'ansible.builtin.assert': {'that': ['k3s_preflight_bearer_successes == [true]',
                                                    'k3s_preflight_registry_token_response == {}']}})
    result = run_tasks(tmp_path, tasks, {
        'k3s_preflight_bearer_successes': [],
        'k3s_registry_challenge': {
            'www_authenticate': 'Bearer realm="https://harbor.synthetic.invalid:883/service/token",service="registry"',
            'item': {'endpoint': 'https://harbor.synthetic.invalid:883',
                     'auth_ref': 'op://synthetic/registry/credentials'}},
    })
    assert result.returncode == 0, result.stdout + result.stderr
