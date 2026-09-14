"""Offline candidate compatibility probe; pass the pinned Collection checkout path."""

import importlib
import sys
import types
from pathlib import Path
from types import SimpleNamespace

source = Path(sys.argv[1]).resolve()
assert (source / 'plugins/modules/nat_destination.py').is_file()
for name, path in [('ansible_collections', source.parent),
                   ('ansible_collections.oxlorg', source.parent),
                   ('ansible_collections.oxlorg.opnsense', source)]:
    module = types.ModuleType(name)
    module.__path__ = [str(path)]
    sys.modules[name] = module

for resource, class_name, field in [('nat_source', 'SNat', 'target_port'),
                                    ('nat_destination', 'DNat', 'local_port'),
                                    ('rule_interface_group', 'Group', 'description'),
                                    ('nat_one_to_one', 'OneToOne', None)]:
    importlib.import_module('ansible_collections.oxlorg.opnsense.plugins.modules.' + resource)
    cls = getattr(importlib.import_module('ansible_collections.oxlorg.opnsense.plugins.module_utils.main.' + resource), class_name)
    params = {key: '' for key in cls.FIELDS_ALL}
    params.update(enabled=True, log=False, source_invert=False, destination_invert=False,
                  no_nat=False, no_port_forward=False, static_port=False, gui_group=True,
                  interface=['wan'] if resource == 'nat_destination' else 'wan',
                  members=['lan'], sequence=10)
    if field:
        params[field] = None
    obj = cls(SimpleNamespace(params=params, check_mode=True), {'changed': False, 'diff': {}}, session=object())
    request = obj._base_build_request()
    body = next(iter(request.values()))
    assert isinstance(body, dict), request
    if field:
        native = cls.FIELDS_TRANSLATE.get(field, field)
        assert body[native] == '', (resource, field)
    if resource == 'nat_source':
        assert obj.simplify_existing(body)['no_nat'] is False
        body['nonat'] = '1'
        assert obj.simplify_existing(body)['no_nat'] is True
    elif resource == 'nat_destination':
        assert body['disabled'] == 0
        assert obj.simplify_existing(body)['no_port_forward'] is False
        body['nordr'] = '1'
        assert obj.simplify_existing(body)['no_port_forward'] is True
    elif resource == 'rule_interface_group':
        assert body['nogroup'] == 0
    print(resource + ': import and request/response conversion passed')

import contextlib
import io
import json
from ansible.module_utils import basic
reload_module = importlib.import_module('ansible_collections.oxlorg.opnsense.plugins.modules.reload')
for target in ('rule_interface_group', 'group'):
    basic._ANSIBLE_PROFILE = 'legacy'
    basic._ANSIBLE_ARGS = json.dumps({'ANSIBLE_MODULE_ARGS': {
        'target': target, 'firewall': 'synthetic.invalid',
        'api_key': 'synthetic', 'api_secret': 'synthetic',
        '_ansible_check_mode': True,
    }}).encode()
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        try:
            reload_module.run_module()
        except SystemExit as exc:
            code = exc.code
    result = json.loads(output.getvalue())
    assert code != 0 and result.get('failed') is True
    assert 'value of target must be one of' in result['msg'], result['msg']
    print('reload target ' + target + ': rejected by actual argument parser')

# 26.7 SourceNatController::getAction returns general settings only.
# Exercise the actual candidate search path using that API response shape.
from ansible_collections.oxlorg.opnsense.plugins.module_utils.main.nat_source import SNat
from ansible_collections.oxlorg.opnsense.plugins.module_utils.base.handler import AnsibleModuleError

for mode in ('automatic', 'hybrid', 'advanced', 'disabled'):
    response = {'filter': {'general': {'snat_mode': mode}}}
    session = SimpleNamespace(get=lambda **kwargs: response)
    obj = SNat(SimpleNamespace(params={}, check_mode=True), {}, session=session)
    try:
        obj.get_existing()
    except AnsibleModuleError as exc:
        assert "Got invalid API_KEY_PATH: 'filter.snatrules.rule'" in str(exc)
    else:
        raise AssertionError('expected candidate SNAT search incompatibility')
print('SNAT 26.7 get response: invalid API_KEY_PATH reproduced in all four modes')
