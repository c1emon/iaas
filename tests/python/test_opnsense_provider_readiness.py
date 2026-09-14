from importlib.util import module_from_spec, spec_from_file_location
import os
from pathlib import Path
import json
import subprocess
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[2]
FILTER_PATH = ROOT / 'automation/ansible/filter_plugins/opnsense_resources.py'
FILTER = module_from_spec(spec_from_file_location('opnsense_resources_readiness', FILTER_PATH))
assert FILTER.__spec__ is not None and FILTER.__spec__.loader is not None
FILTER.__spec__.loader.exec_module(FILTER)


def test_actual_ansible_collection_loader_accepts_locked_dnat_provider(tmp_path: Path) -> None:
    playbook = tmp_path / 'readiness.yml'
    playbook.write_text(
        """\
- hosts: localhost
  gather_facts: false
  connection: local
  tasks:
    - ansible.builtin.assert:
        that:
          - \"'dnat' | opnsense_provider_readiness\"
""",
        encoding='utf-8',
    )
    result = subprocess.run(
        ['uv', 'run', 'ansible-playbook', '-i', 'localhost,', str(playbook)],
        cwd=ROOT,
        env=os.environ | {'ANSIBLE_CONFIG': str(ROOT / 'automation/ansible/ansible.cfg')},
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize('module_path,version', [(None, '26.1.11'), ('module.py', '26.1.10')])
def test_provider_readiness_rejects_missing_module_or_wrong_manifest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, module_path: str | None, version: str
) -> None:
    collection = tmp_path / 'collection'
    collection.mkdir()
    (collection / 'MANIFEST.json').write_text(
        json.dumps({'collection_info': {'version': version}}), encoding='utf-8'
    )
    origin = collection / (module_path or 'nat_destination.py')
    if module_path:
        origin.write_text('# synthetic provider module\n', encoding='utf-8')

    import importlib.util

    def fake_find_spec(name: str):
        if name.endswith('.nat_destination'):
            return SimpleNamespace(origin=str(origin)) if module_path else None
        return None

    monkeypatch.setattr(importlib.util, 'find_spec', fake_find_spec)
    with pytest.raises(ValueError, match='reinstall the locked collection'):
        FILTER.opnsense_provider_readiness('dnat')
