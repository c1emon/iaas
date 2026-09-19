"""Formal runtime operations with two synthetic caller layouts (no appliance)."""
from copy import deepcopy
import json
from pathlib import Path

import pytest
import yaml

from iaas_automation.common.errors import ValidationError
from iaas_automation.opnsense_workflow.runtime import target_from_inventory
from iaas_automation.runtime_config.selection import runtime_platform
from iaas_automation.runtime_execution.__main__ import main
from test_opnsense_workflow import Appliance, TARGET, alias


def test_target_requires_single_host_and_binds_tls():
    inventory = {'all': {'children': {'opnsense': {'vars': {'opnsense_ssl_verify': False},
                 'hosts': {'firewall-a': {'opnsense_api_host': '192.0.2.254'}}}}}}
    assert target_from_inventory(inventory, 'firewall-a')['ssl_verify'] is False
    for scope in ('all', 'firewall-a,firewall-b', 'missing'):
        with pytest.raises(ValidationError):
            target_from_inventory(inventory, scope)


@pytest.mark.parametrize('layout', ['flat', 'nested'])
def test_formal_read_plan_apply_verify_and_fixed_source(tmp_path, monkeypatch, layout):
    import iaas_automation.opnsense_workflow.reader as reader_module
    import iaas_automation.opnsense_workflow.writer as writer_module
    device = Appliance(aliases=[alias('UNMANAGED')])
    device.close = lambda: None
    monkeypatch.setattr(reader_module, 'Reader', lambda *_args: device)
    monkeypatch.setattr(writer_module, 'Writer', lambda *_args, **_kwargs: device)
    root = tmp_path / layout
    root.mkdir()
    declarations = root if layout == 'flat' else root / 'declarations' / 'firewall'
    declarations.mkdir(parents=True, exist_ok=True)
    entry = root / 'environment.yml'
    inputs = declarations / 'aliases.yml'
    inventory = declarations / 'inventory.yml'
    req = declarations / 'request.yml'
    inputs.write_text(yaml.safe_dump({'opnsense_aliases': [alias('A')]}))
    inventory.write_text(yaml.safe_dump({'all': {'children': {'opnsense': {'hosts': {
        TARGET['host']: {'opnsense_api_host': TARGET['endpoint'], 'opnsense_ssl_verify': True}}}}}}))
    req.write_text(yaml.safe_dump({'schema_version': 1, 'selection': {'aliases': 'all'}}))
    component = {'inputs': {'aliases': str(inputs)}, 'files': {'inventory': str(inventory), 'request': str(req)}}

    def invoke(operation, *, options=None):
        current = deepcopy(component)
        if options is not None:
            current['options'] = options
        entry.write_text(yaml.safe_dump({'schema_version': 1, 'environment': 'synthetic',
                                       'components': {'opnsense': current}}))
        args = ['--environment', str(entry), '--component', 'opnsense', '--operation', operation,
                '--scope', TARGET['host'], '--image-digest', 'sha256:' + 'b' * 64,
                '--output', str(tmp_path / ('execution-1' if operation == 'apply' else operation))]
        if operation == 'apply':
            args.extend(['--execution-id', 'execution-1'])
        return main(args)

    assert invoke('read') == 0
    assert not device.calls
    assert invoke('plan') == 0
    candidate = tmp_path / 'plan/plan/candidate.json'
    summary = json.loads((tmp_path / 'plan/plan/result.json').read_text())
    component['files']['candidate'] = str(candidate)
    # Apply and verify must never reopen changed/missing desired inputs.
    inputs.unlink()
    digest = summary['candidate_sha256']
    options = {'candidate_sha256': digest, 'execution_id': 'execution-1',
               'activation_check': {'target': TARGET, 'candidate_sha256': digest, 'execution_id': 'execution-1',
                                    'checked_no_pending': True, 'serialized': True}}
    assert invoke('apply', options=options) == 0
    assert {row['name'] for row in device.resources['aliases']} == {'UNMANAGED', 'A'}
    assert invoke('verify') == 0
    for path in (candidate, tmp_path / 'execution-1/recovery/recovery.json'):
        assert path.stat().st_mode & 0o777 == 0o600
    assert json.loads((tmp_path / 'verify/diagnostics/result.json').read_text())['status'] == 'completed_with_unverified'
