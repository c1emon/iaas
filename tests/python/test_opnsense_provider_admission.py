"""Exercise the pinned Collection's real validation without network access."""
import json
import os
from pathlib import Path
import subprocess

import pytest

from iaas_automation.common.errors import ValidationError
from iaas_automation.opnsense_validation.aliases import validate_url


ROOT = Path(__file__).resolve().parents[2]
COLLECTIONS = ROOT / 'automation/ansible/collections'


@pytest.mark.parametrize('kind', ['alias', 'rule'])
def test_provider_verification_failure_is_fatal_with_product_settings(kind):
    # Use actual argument parsing, callbacks and check/process exception handling.
    # Only the external session and existing-object read are replaced.
    script = r'''
import contextlib, importlib, io, json, os
from pathlib import Path
import yaml
from ansible.module_utils import basic
from ansible_collections.oxlorg.opnsense.plugins.module_utils.base import multi
from iaas_automation.common.errors import ValidationError
from iaas_automation.opnsense_validation import validate_document
kind = os.environ['TEST_PROVIDER_KIND']
root = Path.cwd()
playbooks = root / 'automation/ansible/playbooks/opnsense'
if kind == 'alias':
    record = dict(name='TABLE', type='urltable', content=['https://[2001:db8::1]/list'],
                  description='Synthetic', enabled=True, state='present', updatefreq_days='1')
    resource, key = 'aliases', 'opnsense_aliases'
    controls = yaml.safe_load((playbooks / 'tasks/apply-alias-batch.yml').read_text())[0]['oxlorg.opnsense.alias_multi']['multi_control']
else:
    record = yaml.safe_load((root / 'tests/fixtures/opnsense-capabilities/filter-rules.yml').read_text())['opnsense_filter_rules'][0]
    record['sequence'] = 100000
    resource, key = 'filter-rules', 'opnsense_filter_rules'
    play = yaml.safe_load((playbooks / 'manage-filter-rules.yml').read_text())[0]
    task = next(t for t in play['tasks'] if t['name'].startswith('Reconcile declared'))['block'][0]
    controls = task['oxlorg.opnsense.rule_multi']['multi_control']
try:
    validate_document(resource, {key: [record]})
except ValidationError:
    pass
else:
    raise AssertionError('offline validation accepted a provider-incompatible value')
if kind == 'rule':
    record['description'] = 'iaas:opnsense:filter:' + record.pop('scope') + ':' + record.pop('slug')
    for field in ('source_net', 'destination_net', 'source_port', 'destination_port'):
        if isinstance(record.get(field), list): record[field] = ','.join(map(str, record[field]))
provider = importlib.import_module('ansible_collections.oxlorg.opnsense.plugins.modules.' + kind + '_multi')
entry = getattr(importlib.import_module('ansible_collections.oxlorg.opnsense.plugins.module_utils.main.' + kind), kind.title())
class OfflineSession:
    def __init__(self, **kwargs): pass
    def close(self): pass
multi.Session = OfflineSession
entry.get_existing = lambda self: []
def unexpected_write(self): raise AssertionError('rejected declaration reached mutation')
entry.create = unexpected_write
params = dict(firewall='synthetic.invalid', api_key='synthetic', api_secret='synthetic',
              ssl_verify=False, reload=False, multi_control=controls)
params['aliases' if kind == 'alias' else 'rules'] = [record]
if kind == 'rule': params['match_fields'] = ['description']
basic._ANSIBLE_PROFILE = 'legacy'
basic._ANSIBLE_ARGS = json.dumps({'ANSIBLE_MODULE_ARGS': params}).encode()
captured = io.StringIO()
with contextlib.redirect_stdout(captured):
    try: provider.run_module()
    except SystemExit as error: code = error.code
result = json.loads(captured.getvalue())
assert code != 0 and result.get('failed') is True, result
print(json.dumps({'failed': result['failed'], 'code': code}))
'''
    result = subprocess.run(['uv', 'run', 'python', '-c', script], cwd=ROOT, capture_output=True, text=True,
                            env=os.environ | {'TEST_PROVIDER_KIND': kind,
                                              'PYTHONPATH': os.pathsep.join([str(ROOT / 'automation/src'), str(COLLECTIONS)])})
    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(result.stdout)['failed'] is True


def test_url_shapes_agree_with_pinned_provider():
    cases = {
        'https://lists.example.invalid/table?v=1': True,
        'http://192.0.2.1:8080/list': True,
        'https://[2001:db8::1]/list': False,
        'https://firewall/list': False,
        'https://example.invalid:1/list': False,
        'http://192.0.2.255/list': False,
    }
    result = subprocess.run([
        'uv', 'run', 'python', '-c',
        'import json,sys; from ansible_collections.oxlorg.opnsense.plugins.module_utils.helper.validate import is_valid_url; '
        'print(json.dumps({u:is_valid_url(u) for u in json.loads(sys.argv[1])}))', json.dumps(list(cases)),
    ], cwd=ROOT, capture_output=True, text=True, env=os.environ | {'PYTHONPATH': str(COLLECTIONS)})
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == cases
    for url, accepted in cases.items():
        if accepted:
            validate_url(url, 'url')
        else:
            with pytest.raises(ValidationError):
                validate_url(url, 'url')
