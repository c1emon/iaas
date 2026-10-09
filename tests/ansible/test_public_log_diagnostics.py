"""Actual callback metadata preserves protected failures and warning presence."""
import json
import os
from pathlib import Path
import subprocess

import pytest
import yaml

from iaas.common.public_diagnostics import MARKER


ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize('protected', [False, True])
@pytest.mark.parametrize('looped', [False, True])
def test_callback_preserves_error_and_warning_metadata_without_protected_text(tmp_path, protected, looped):
    library = tmp_path / 'library'
    library.mkdir()
    (library / 'synthetic_failure.py').write_text(
        'from ansible.module_utils.basic import AnsibleModule\n'
        'module = AnsibleModule(argument_spec={})\n'
        'module.warn("private-warning-sentinel")\n'
        'module.fail_json(msg="private-error-sentinel", rc=8)\n')
    task = {'name': 'Synthetic failure', 'synthetic_failure': {}, 'no_log': protected}
    if looped:
        task['loop'] = ['private-item-sentinel']
    playbook = tmp_path / 'failure.yml'
    playbook.write_text(yaml.safe_dump([{'hosts': 'localhost', 'connection': 'local',
                                       'gather_facts': False, 'tasks': [task]}]))
    result = subprocess.run(['uv', 'run', 'ansible-playbook', '-i', 'localhost,', str(playbook)],
        cwd=ROOT, env=os.environ | {'ANSIBLE_CONFIG': str(ROOT / 'automation/ansible/ansible.cfg'),
                                   'ANSIBLE_LIBRARY': str(library), 'ANSIBLE_LOCAL_TEMP': str(tmp_path / 'ansible')},
        capture_output=True, text=True, timeout=30)
    output = result.stdout + result.stderr
    assert result.returncode != 0
    entries = [json.loads(line.split(MARKER, 1)[1]) for line in output.splitlines() if line.startswith(MARKER)]
    prefix = 'protected_' if protected else ''
    assert any(entry['code'] == prefix + 'task_failed' for entry in entries)
    assert any(entry['code'] == ('protected_warning' if protected else 'task_warning') for entry in entries)
    if protected:
        assert 'private-' not in output
    else:
        assert 'private-error-sentinel' in output and 'private-warning-sentinel' in output


@pytest.mark.parametrize('message,expected', [
    ('K3s runtime service failed the post-restart health gate', 'k3s_runtime_unhealthy'),
    ('private-custom-failure', 'protected_task_failed'),
])
def test_protected_assertion_gate_reports_only_recognized_static_reason(tmp_path, message, expected):
    playbook = tmp_path / 'assert.yml'
    playbook.write_text(yaml.safe_dump([{'hosts': 'localhost', 'connection': 'local', 'gather_facts': False,
        'tasks': [{'name': 'Synthetic admission gate', 'no_log': True,
                   'ansible.builtin.assert': {'that': ['false'], 'fail_msg': message}}]}]))
    result = subprocess.run(['uv', 'run', 'ansible-playbook', '-i', 'localhost,', str(playbook)],
        cwd=ROOT, env=os.environ | {'ANSIBLE_CONFIG': str(ROOT / 'automation/ansible/ansible.cfg'),
                                   'ANSIBLE_LOCAL_TEMP': str(tmp_path / 'ansible')},
        capture_output=True, text=True, timeout=30)
    output = result.stdout + result.stderr
    assert result.returncode != 0
    assert expected in output
    assert 'private-custom-failure' not in output
