"""CI and runtime must exercise the same shipped dependency baseline."""
import json
from pathlib import Path
import re
import yaml

ROOT = Path(__file__).resolve().parents[2]


def test_ci_runs_native_opentofu_without_action_wrapper():
    # Protected native subprocesses intentionally do not inherit the action's
    # TOFU_CLI_PATH, output-file channels or other runner bootstrap environment.
    for filename, job in (('offline-validation.yml', 'check'), ('runtime-release.yml', 'build')):
        workflow = yaml.safe_load((ROOT / '.github/workflows' / filename).read_text())
        setup = next(step for step in workflow['jobs'][job]['steps']
                     if step.get('uses', '').startswith('opentofu/setup-opentofu@'))
        assert setup['with']['tofu_wrapper'] is False


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


def test_image_jobs_use_one_platform_capable_docker_baseline():
    baseline = []
    for filename, names in (
        ('offline-validation.yml', ('runtime',)),
        ('runtime-release.yml', ('build', 'publish', 'anonymous-consumption')),
    ):
        jobs = yaml.safe_load((ROOT / '.github/workflows' / filename).read_text())['jobs']
        for name in names:
            steps = jobs[name]['steps']
            setup_index, setup = next(
                (index, step) for index, step in enumerate(steps)
                if step.get('uses', '').startswith('docker/setup-docker-action@')
            )
            assert re.fullmatch(r'docker/setup-docker-action@[0-9a-f]{40}', setup['uses'])
            settings = setup['with']
            assert settings['version'] == 'v29.5.2'
            # Temporary DOCKER_CONFIG directories must not lose the selected daemon.
            assert settings['set-host'] is True
            assert json.loads(settings['daemon-config'])['features']['containerd-snapshotter'] is True
            baseline.append((setup['uses'], settings))
            first_image_command = next(
                index for index, step in enumerate(steps)
                if re.search(r'\bdocker\b|make runtime-', step.get('run', ''))
            )
            assert setup_index < first_image_command
    assert all(item == baseline[0] for item in baseline)


def test_ci_upload_uses_injected_token_without_local_shell_bootstrap():
    workflow = yaml.safe_load((ROOT / '.github/workflows/runtime-release.yml').read_text())
    job = workflow['jobs']['launcher']
    upload = next(step for step in job['steps'] if 'gh release upload' in step.get('run', ''))
    assert upload['shell'] == 'bash'
    assert upload['env']['GH_TOKEN'] == '${{ github.token }}'
    assert job['permissions'] == {'contents': 'write'}
    # Neither workflow may acquire credentials through a local 1Password session.
    for filename in ('offline-validation.yml', 'runtime-release.yml'):
        content = (ROOT / '.github/workflows' / filename).read_text()
        assert not re.search(r'(?i)\b1password\b|\bop\s+(run|signin|read|inject)\b|OP_SERVICE_ACCOUNT_TOKEN|zsh\s+-li', content)
