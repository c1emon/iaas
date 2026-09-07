"""Exercise real role expressions through Ansible's native templating."""
import pytest
import yaml

from test_k3s_first_boot import ANSIBLE, run_tasks


@pytest.mark.parametrize('role', ['k3s_preflight', 'k3s_acquisition'])
@pytest.mark.parametrize('proxy', [None, '', 'http://proxy.invalid:3128'])
def test_artifact_proxy_has_no_template_whitespace(tmp_path, role, proxy):
    source = yaml.safe_load((ANSIBLE / f'roles/{role}/tasks/main.yml').read_text())
    task = next(t for t in source if 'environment' in t)
    result = run_tasks(tmp_path, [
        {'ansible.builtin.set_fact': {'rendered': task['environment']}},
        {'ansible.builtin.assert': {'that': [
            'rendered.https_proxy == expected', 'rendered.HTTPS_PROXY == expected']}}
    ], {f'{role}_artifact': {'credential_ref': None, 'proxy_url': proxy},
        'expected': proxy or ''})
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize('rc,stdout,expected', [(0, '', True), (0, 'LISTEN', False), (1, '', False)])
def test_port_probe_boolean_has_no_template_whitespace(tmp_path, rc, stdout, expected):
    source = yaml.safe_load((ANSIBLE / 'roles/k3s_preflight/tasks/main.yml').read_text())
    task = next(t for t in source if t['name'] == 'Build runtime facts from read-only probes')
    expression = task['ansible.builtin.set_fact']['k3s_preflight_runtime']['ports_available']
    result = run_tasks(tmp_path, [
        {'ansible.builtin.set_fact': {'ports': expression}},
        {'ansible.builtin.assert': {'that': ['ports is boolean', 'ports == expected']}}
    ], {'k3s_preflight_probes': {'results': [{}, {}, {}, {}, {'rc': 0}]},
        'k3s_preflight_port_checks': {'results': [{'rc': rc, 'stdout': stdout}]},
        'expected': expected})
    assert result.returncode == 0, result.stdout + result.stderr
