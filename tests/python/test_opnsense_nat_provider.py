"""Representative offline checks of the installed, pinned Collection."""
import os
from pathlib import Path
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[2]
LIFECYCLE = ROOT / 'tests/fixtures/opnsense-nat/provider_lifecycle.py'


@pytest.mark.parametrize('resource', ['nat_destination', 'nat_one_to_one', 'rule_interface_group'])
def test_candidate_check_mode_does_not_write(resource):
    script = r'''
import contextlib, importlib, io, json, os
from ansible.module_utils import basic
from ansible_collections.oxlorg.opnsense.plugins.module_utils.base import logic

class OfflineSession:
    def __init__(self, **kwargs): pass
    def close(self): pass
    def get(self, cnf):
        assert cnf['command'] == 'get'
        return {'DNat': {'rule': {}}, 'filter': {'onetoone': {'rule': {}}},
                'group': {'ifgroupentry': {}}}
    def post(self, **kwargs):
        raise AssertionError('check mode reached a device write or activation')

logic.Session = OfflineSession
resource = os.environ['TEST_NAT_PROVIDER']
params = dict(firewall='synthetic.invalid', api_key='synthetic', api_secret='synthetic',
              state='present', reload=True, _ansible_check_mode=True)
if resource == 'rule_interface_group':
    params.update(name='Internal', members=['lan'], gui_group=True, sequence=10, description='')
else:
    params.update(description='iaas:opnsense:test:sample:rule', match_fields=['description'],
                  enabled=True, sequence=10, interface='wan', source_net='192.0.2.1',
                  destination_net='any', log=False)
    if resource == 'nat_destination':
        params.update(interface=['wan'], ip_protocol='inet', protocol='TCP',
                      target='192.0.2.2', nat_reflection='', associated_rule='rule')
    else:
        params.update(type='binat', external='198.51.100.1', nat_reflection='disable')
basic._ANSIBLE_PROFILE = 'legacy'
basic._ANSIBLE_ARGS = json.dumps({'ANSIBLE_MODULE_ARGS': params}).encode()
provider = importlib.import_module('ansible_collections.oxlorg.opnsense.plugins.modules.' + resource)
output = io.StringIO()
with contextlib.redirect_stdout(output):
    try: provider.run_module()
    except SystemExit as error: code = error.code
result = json.loads(output.getvalue())
assert code == 0 and result['changed'] is True, result
print('check mode predicted creation without writes')
'''
    result = subprocess.run(['uv', 'run', 'python', '-c', script], cwd=ROOT,
                            capture_output=True, text=True,
                            env=os.environ | {'TEST_NAT_PROVIDER': resource,
                                              'PYTHONPATH': str(ROOT / 'automation/ansible/collections')})
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize('resource', ['nat_destination', 'nat_one_to_one', 'rule_interface_group'])
def test_candidate_lifecycle_uses_real_module_and_fixture_arguments(resource):
    result = subprocess.run(
        ['uv', 'run', 'python', str(LIFECYCLE)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        env=os.environ | {
            'TEST_NAT_PROVIDER': resource,
            'PYTHONPATH': os.pathsep.join([
                str(ROOT / 'automation/src'),
                str(ROOT / 'automation/ansible/collections'),
            ]),
        },
    )
    assert result.returncode == 0, result.stdout + result.stderr
