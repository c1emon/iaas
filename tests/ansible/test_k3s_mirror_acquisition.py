"""Both admission layers accept the same pinned URLs, without downloading."""
import os
from pathlib import Path
import subprocess

import pytest
import yaml

from iaas_automation.common.errors import ValidationError
from iaas_automation.k3s_automation.config import build_composed_model

ROOT = Path(__file__).resolve().parents[2]
VERSION = 'v1.35.1+k3s1'
CN = 'https://rancher-mirror.rancher.cn/k3s/v1.35.1-k3s1/k3s'


@pytest.mark.parametrize('url,checksum,valid', [
    (CN, 'a' * 64, True),
    ('https://github.com/k3s-io/k3s/releases/download/' + VERSION + '/k3s', 'a' * 64, True),
    ('https://internal.synthetic.invalid/' + VERSION + '/k3s', 'a' * 64, True),
    (CN.replace('1.35.1', '1.35.0'), 'a' * 64, False),
    (CN.replace('rancher-mirror.rancher.cn', 'other.invalid'), 'a' * 64, False),
    (CN.replace('https:', 'http:'), 'a' * 64, False),
    (CN + '?version=' + VERSION, 'a' * 64, False),
    (CN + '-arm64', 'a' * 64, False),
    (CN, '', False),
])
def test_model_and_role_agree_without_acquiring_binary(tmp_path, url, checksum, valid):
    fixture = ROOT / 'tests/fixtures/k3s'
    intent = yaml.safe_load((fixture / 'intent.yml').read_text())
    inventory = yaml.safe_load((fixture / 'generated-pve.yml').read_text())
    artifact = {'url': url, 'sha256': checksum}
    intent['cluster']['artifacts']['amd64'] = artifact
    if valid:
        model = build_composed_model(intent, inventory)
        assert model['cluster']['artifacts']['amd64']['url'] == url
        assert model['cluster']['version'] == VERSION
    else:
        with pytest.raises(ValidationError):
            build_composed_model(intent, inventory)
    role = yaml.safe_load((ROOT / 'automation/ansible/roles/k3s_acquisition/tasks/main.yml').read_text())
    # Only the real input assertions and artifact selection; deliberately exclude get_url.
    tasks = role[:3]
    assert all('ansible.builtin.get_url' not in task for task in tasks)
    playbook = tmp_path / 'admission.yml'
    playbook.write_text(yaml.safe_dump([{
        'hosts': 'localhost', 'connection': 'local', 'gather_facts': False,
        'vars': {'k3s_acquisition_model_node': {'architecture': 'amd64'},
                 'k3s_acquisition_cluster': {'version': VERSION, 'artifacts': {'amd64': artifact}}},
        'tasks': tasks,
    }]))
    result = subprocess.run(['uv', 'run', 'ansible-playbook', '-i', 'localhost,', str(playbook)],
                            cwd=ROOT, capture_output=True, text=True, check=False,
                            env=dict(os.environ, ANSIBLE_CONFIG=str(ROOT / 'automation/ansible/ansible.cfg')))
    assert (result.returncode == 0) == valid, result.stdout + result.stderr
