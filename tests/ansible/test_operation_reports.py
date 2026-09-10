"""Representative report redaction and two-target local export orchestration."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
ANSIBLE = ROOT / 'automation/ansible'
spec = importlib.util.spec_from_file_location('operation_reports', ANSIBLE / 'filter_plugins/operation_reports.py')
reports = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reports)


def test_switch_summary_contains_object_changes_without_payloads():
    summary = reports.switch_plan_summary({'vlans': {'results': [{
        'before': [{'vlan_id': 10, 'name': 'private-before'}],
        'after': [{'vlan_id': 10, 'name': 'private-after'}, {'vlan_id': 20}],
        'commands': ['sensitive-command'],
    }]}})
    assert summary['changed_objects'] == 2
    assert summary['changes'][0] == {'resource': 'vlans', 'call': 1, 'object': '10',
                                     'change': 'updated', 'fields': ['name']}
    assert 'private' not in json.dumps(summary)
    assert 'sensitive' not in json.dumps(summary)
    assert reports.switch_plan_summary({'vlans': {'results': [{'before': [], 'after': []}]}})['changed_objects'] == 0
    with pytest.raises(ValueError, match='before/after'):
        reports.switch_plan_summary({'vlans': {'results': [{}]}})


def test_report_path_rejects_inputs_and_traversal(tmp_path):
    for target in ['../fw', '.', 'fw/a']:
        with pytest.raises(ValueError):
            reports.protected_report_directory(str(tmp_path), target)
    with pytest.raises(ValueError, match='overlaps'):
        reports.protected_report_directory(str(ROOT / 'automation'), 'fw')
    (tmp_path / 'fw').symlink_to(tmp_path / 'elsewhere')
    with pytest.raises(ValueError):
        reports.protected_report_directory(str(tmp_path), 'fw')


def test_two_target_exports_are_attributed_private_and_separate(tmp_path):
    original = yaml.safe_load((ANSIBLE / 'playbooks/opnsense/export.yml').read_text())[0]
    tasks = [task for task in original['tasks'] if not any(
        key in task for key in ['ansible.builtin.import_tasks', 'oxlorg.opnsense.list', 'oxlorg.opnsense.raw'])]
    variables = original['vars'] | {
        'opnsense_export_dir': str(tmp_path / 'exports'),
        'opnsense_config_candidate_results': {'results': [{
            'item': {'name': 'firewall-aliases', 'target': 'alias', 'description': 'Aliases'},
            'data': 'private-topology',
        }]},
        'opnsense_dhcp_fact_results': {'results': [{
            'item': {'name': 'dhcpv4-leases', 'module': 'dhcpv4', 'controller': 'leases',
                     'command': 'search_lease', 'description': 'Leases'},
            'data': 'private-lease',
        }]},
    }
    play = [{'hosts': 'all', 'connection': 'local', 'gather_facts': False, 'vars': variables, 'tasks': tasks}]
    result = subprocess.run(['uv', 'run', 'ansible-playbook', '-i', 'fw-a,fw-b,', '/dev/stdin'],
                            input=yaml.safe_dump(play), text=True, capture_output=True, cwd=ROOT,
                            env=os.environ | {'ANSIBLE_CONFIG': str(ANSIBLE / 'ansible.cfg'),
                                              'ANSIBLE_LOCAL_TEMP': str(tmp_path / 'local')})
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'private-topology' not in result.stdout and 'private-lease' not in result.stdout
    for host in ['fw-a', 'fw-b']:
        directory = tmp_path / 'exports' / host
        assert directory.stat().st_mode & 0o777 == 0o700
        for filename in ['firewall-aliases.json', 'dhcpv4-leases.json']:
            path = directory / filename
            assert path.stat().st_mode & 0o777 == 0o600
            assert json.loads(path.read_text())['device'] == host


def test_switch_summary_and_optional_detail_use_real_tasks(tmp_path):
    preview = {'vlans': {'results': [{'before': [], 'after': [{'vlan_id': 20, 'name': 'private-vlan'}],
                                      'commands': ['private-command']}]}}
    diff = yaml.safe_load((ANSIBLE / 'roles/switch_config/tasks/diff.yml').read_text())
    export = yaml.safe_load((ANSIBLE / 'roles/switch_config/tasks/export.yml').read_text())
    tasks = [task for task in diff if task['name'] == 'Report sanitized object changes'] + export
    variables = {'switch_config_collection_preview': preview, 'switch_config_resources': {},
                 'switch_config_requested_calls': [], 'switch_config_allowed_states': ['merged'],
                 'switch_config_apply': False, 'switch_config_detail_dir': str(tmp_path / 'detail')}
    result = subprocess.run(['uv', 'run', 'ansible-playbook', '-i', 'sw-a,', '/dev/stdin'],
                            input=yaml.safe_dump([{'hosts': 'all', 'gather_facts': False,
                                                  'connection': 'local', 'vars': variables, 'tasks': tasks}]),
                            text=True, capture_output=True, cwd=ROOT,
                            env=os.environ | {'ANSIBLE_CONFIG': str(ANSIBLE / 'ansible.cfg')})
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'changed_objects: 1' in result.stdout
    assert 'private-vlan' not in result.stdout and 'private-command' not in result.stdout
    path = tmp_path / 'detail/sw-a/plan.json'
    assert path.stat().st_mode & 0o777 == 0o600
    assert json.loads(path.read_text())['target'] == 'sw-a'
    assert 'private-command' in path.read_text()
