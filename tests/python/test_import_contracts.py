"""Prove the configured import boundaries reject synthetic violations."""
from pathlib import Path
import os
import subprocess
import sys
import tomllib
import pytest

pytestmark = pytest.mark.integration


def test_import_contracts_reject_each_boundary(tmp_path):
    root = Path(__file__).resolve().parents[2]
    config = root / 'pyproject.toml'
    contracts = tomllib.loads(config.read_text())['tool']['importlinter']['contracts']
    for contract in contracts:
        for name in contract['source_modules'] + contract['forbidden_modules']:
            if not name.startswith('iaas_automation'):
                continue
            path = tmp_path
            for part in name.split('.'):
                path /= part
                path.mkdir(exist_ok=True)
                (path / '__init__.py').touch()
    command = [str(Path(sys.executable).parent / 'lint-imports'), '--config', str(config), '--no-cache']
    env = dict(os.environ, PYTHONPATH=str(tmp_path))
    baseline = subprocess.run(command, cwd=tmp_path, env=env, capture_output=True, text=True)
    assert baseline.returncode == 0, baseline.stdout
    for contract in contracts:
        source = tmp_path.joinpath(*contract['source_modules'][0].split('.')) / '__init__.py'
        source.write_text('import ' + contract['forbidden_modules'][0] + '\n')
        try:
            result = subprocess.run(command, cwd=tmp_path, env=env, capture_output=True, text=True)
            assert result.returncode == 1, result.stdout
            assert contract['name'] + ' BROKEN' in result.stdout
        finally:
            source.write_text('')
