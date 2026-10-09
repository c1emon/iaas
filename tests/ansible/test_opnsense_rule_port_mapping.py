"""Run both Jinja provider conversions with local synthetic records only."""
from copy import deepcopy
import os
from pathlib import Path
import subprocess

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'automation/ansible/playbooks/opnsense'


@pytest.mark.parametrize('workflow', [False, True])
@pytest.mark.parametrize('invalid', [False, True])
def test_rule_conversion_uses_shared_constraint_before_any_provider_write(tmp_path, workflow, invalid):
    source = yaml.safe_load((BASE / ('tasks/workflow-stage-save.yml' if workflow else
                                   'manage-filter-rules.yml')).read_text())
    if workflow:
        task = next(task for task in source[1]['block']
                    if task['name'] == 'Build fixed provider filter-rule records')
        result_key = 'opnsense_workflow_filter_rules'
    else:
        task = next(task for task in source[0]['tasks']
                    if task['name'] == 'Generate module-compatible OPNsense new filter rules')
        result_key = 'opnsense_filter_rule_apply_rules'
    template = yaml.safe_load((ROOT / 'tests/fixtures/environment/ansible/vars/opnsense/filter-rules.yml').read_text())['opnsense_filter_rules'][0]
    rows = [dict(deepcopy(template), slug=f'ports-{index}', destination_port=value)
            for index, value in enumerate([443, ['8848-9848'], 'NACOS_PORTS'])]
    if invalid:
        rows.append(dict(deepcopy(template), slug='invalid', destination_port=[8848, 9848]))
    marker = tmp_path / 'provider-called'
    playbook = tmp_path / 'mapping.yml'
    playbook.write_text(yaml.safe_dump([{
        'hosts': 'localhost', 'connection': 'local', 'gather_facts': False,
        'vars': {'opnsense_filter_rules': rows, result_key: [],
                 'opnsense_workflow_resource': 'filter-rules',
                 'opnsense_workflow_key': 'opnsense_filter_rules'},
        'tasks': [task, {'ansible.builtin.assert': {'that': [
            f"{result_key}[0].destination_port == '443'",
            f"{result_key}[1].destination_port == '8848-9848'",
            f"{result_key}[2].destination_port == 'NACOS_PORTS'",
        ]}}, {'ansible.builtin.copy': {'content': 'synthetic write', 'dest': str(marker), 'mode': '0600'}}],
    }], sort_keys=False))
    result = subprocess.run(['uv', 'run', 'ansible-playbook', '-i', 'localhost,', str(playbook)],
        cwd=ROOT, env=os.environ | {
            'ANSIBLE_CONFIG': str(ROOT / 'automation/ansible/ansible.cfg'),
            'ANSIBLE_LOCAL_TEMP': str(tmp_path / 'ansible'),
        }, capture_output=True, text=True, timeout=30)
    output = result.stdout + result.stderr
    if invalid:
        assert result.returncode != 0
        assert not marker.exists()
        assert 'destination_port' in output and 'explicit port alias' in output
    else:
        assert result.returncode == 0, output
        assert marker.exists()
