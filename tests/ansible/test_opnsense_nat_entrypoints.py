"""Exercise actual loaded-input checks with no device credentials."""
from pathlib import Path
import os
import subprocess

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
ANSIBLE = ROOT / 'automation/ansible'


def run_new_resource_entrypoint(tmp_path, resource, source_variable, document_key):
    doc = yaml.safe_load((ROOT / f'tests/fixtures/opnsense-nat/{resource}.yml').read_text())
    source = tmp_path / 'source.yml'
    source.write_text(yaml.safe_dump(doc))
    invalid = dict(doc[document_key][0], unexpected_option=True)
    overrides = tmp_path / 'overrides.yml'
    overrides.write_text(yaml.safe_dump({source_variable: str(source), document_key: [invalid]}))
    return subprocess.run([
        'uv', 'run', 'ansible-playbook', '-i', 'opnsense,', '--limit', 'opnsense',
        str(ANSIBLE / f'playbooks/opnsense/manage-{resource}.yml'), '--check', '-e', f'@{overrides}',
    ], cwd=ROOT, capture_output=True, text=True,
        env=os.environ | {'ANSIBLE_CONFIG': str(ANSIBLE / 'ansible.cfg')})


@pytest.mark.parametrize('resource,source_variable,document_key', [
    ('one-to-one-nat', 'opnsense_one_to_one_nat_source', 'opnsense_one_to_one_nat_rules'),
    ('interface-groups', 'opnsense_interface_group_source', 'opnsense_interface_groups'),
])
def test_loaded_extra_vars_rejected_before_credentials(tmp_path, resource, source_variable, document_key):
    result = run_new_resource_entrypoint(tmp_path, resource, source_variable, document_key)
    output = result.stdout + result.stderr
    assert result.returncode != 0
    assert 'unexpected_option' in output
    assert 'TASK [Run OPNsense API credential preflight]' not in output
    assert 'Read existing' not in output


def test_actual_filter_guard_accepts_group_context_and_preserves_safety(tmp_path):
    original = yaml.safe_load((ANSIBLE / 'playbooks/opnsense/manage-filter-rules.yml').read_text())[0]
    task = next(row for row in original['tasks'] if row['name'].startswith('Revalidate loaded rules'))
    rules = [dict(scope='test', slug='deny-external', state='present', enabled=True, sequence=10,
                  interface=['Internal'], direction='in', action='block', quick=True,
                  ip_protocol='inet', protocol='any', source_net='any',
                  destination_net='LOCAL_NETS', destination_invert=True)]
    context = {'interface_networks': {'Internal': ['192.0.2.0/24']}, 'aliases': [
        dict(name='LOCAL_NETS', type='network', content=['192.0.2.0/24'],
             description='Synthetic local networks', enabled=True, state='present')]}
    playbook = tmp_path / 'loaded-group.yml'
    playbook.write_text(yaml.safe_dump([{'hosts': 'localhost', 'gather_facts': False,
        'vars': {'opnsense_filter_rules': rules, 'opnsense_filter_rule_context': context},
        'tasks': [task]}]))
    result = subprocess.run(['uv', 'run', 'ansible-playbook', '-i', 'localhost,', str(playbook)],
                            cwd=ROOT, capture_output=True, text=True,
                            env=os.environ | {'ANSIBLE_CONFIG': str(ANSIBLE / 'ansible.cfg')})
    assert result.returncode == 0, result.stdout + result.stderr
