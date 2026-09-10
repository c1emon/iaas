"""CI and runtime must exercise the same shipped dependency baseline."""
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[2]


def test_ci_uses_runtime_tools_and_explicit_collection_closure():
    local = yaml.safe_load((ROOT / 'automation/ansible/requirements.yml').read_text())
    runtime = yaml.safe_load((ROOT / 'automation/runtime/collections.yml').read_text())
    assert local == runtime
    assert all(item.get('version') and not any(c in item['version'] for c in '<>=*')
               for item in local['collections'])
    workflow = yaml.safe_load((ROOT / '.github/workflows/offline-validation.yml').read_text())
    steps = workflow['jobs']['check']['steps']
    tofu = next(step['with']['tofu_version'] for step in steps if 'opentofu/setup-opentofu' in step.get('uses', ''))
    uv = next(step['with']['version'] for step in steps if 'astral-sh/setup-uv' in step.get('uses', ''))
    dockerfile = (ROOT / 'automation/runtime/Dockerfile').read_text()
    assert f'/uv/releases/download/{uv}/' in dockerfile
    assert f'/opentofu/releases/download/v{tofu}/' in dockerfile
    install = next(step['run'] for step in steps if 'ansible-galaxy' in step.get('run', ''))
    assert '--no-deps' in install
    assert dockerfile.index('COPY pyproject.toml uv.lock') < dockerfile.index('COPY automation/src/')
