"""Exercise Ansible's actual extra-vars parser for image package transport."""
import json

import pytest
from ansible import context
from ansible.module_utils.common.collections import ImmutableDict
from ansible.parsing.dataloader import DataLoader
from ansible.parsing.splitter import parse_kv
from ansible.utils.vars import load_extra_vars


@pytest.mark.parametrize('upgrade', [True, False])
def test_nonempty_package_json_and_typed_upgrade_survive_ansible(monkeypatch, upgrade):
    packages = ['sudo', 'vim', 'htop', 'curl', 'wget', 'ca-certificates', 'bash-completion']
    encoded = json.dumps(packages)
    # The old key=value path fails even though an empty list happens to work.
    with pytest.raises(json.JSONDecodeError):
        json.loads(parse_kv('packages_json=' + encoded)['packages_json'])
    monkeypatch.setattr(context, 'CLIARGS', ImmutableDict(extra_vars=[json.dumps({
        'packages_json': encoded, 'image_package_upgrade': upgrade,
        'apt_mirror': 'https://mirrors.tuna.tsinghua.edu.cn/debian',
    })]))
    loader = DataLoader()
    monkeypatch.setattr(load_extra_vars, 'extra_vars', None, raising=False)
    actual = load_extra_vars(loader)
    assert json.loads(actual['packages_json']) == packages
    assert actual['image_package_upgrade'] is upgrade
    assert actual['apt_mirror'] == 'https://mirrors.tuna.tsinghua.edu.cn/debian'
