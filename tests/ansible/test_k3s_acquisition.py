"""Static and offline contract coverage for pinned K3s executable acquisition."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess

import yaml


ROOT = Path(__file__).resolve().parents[2]
ROLE = ROOT / "automation" / "ansible" / "roles" / "k3s_acquisition" / "tasks" / "main.yml"
DEFAULTS = ROOT / "automation" / "ansible" / "roles" / "k3s_acquisition" / "defaults" / "main.yml"


def _run(playbook: Path, *extra: str) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment["ANSIBLE_CONFIG"] = str(ROOT / "automation" / "ansible" / "ansible.cfg")
    return subprocess.run(
        ["uv", "run", "ansible-playbook", "--check", "-i", "localhost,", str(playbook), *extra],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )


def _write_role_playbook(path: Path, artifact: dict[str, object], **variables: object) -> None:
    model_node = {"architecture": "amd64"}
    cluster = {"version": "v1.35.1+k3s1", "artifacts": {"amd64": artifact}}
    path.write_text(
        yaml.safe_dump(
            [
                {
                    "name": "Synthetic K3s acquisition role test",
                    "hosts": "all",
                    "gather_facts": False,
                    "connection": "local",
                    "vars": {
                        "k3s_acquisition_model_node": model_node,
                        "k3s_acquisition_cluster": cluster,
                        **variables,
                    },
                    "roles": ["k3s_acquisition"],
                }
            ],
            sort_keys=False,
        ),
        encoding="utf-8",
    )


def test_acquisition_is_pinned_to_the_composed_architecture_and_checksum() -> None:
    source = ROLE.read_text(encoding="utf-8")

    assert "k3s_acquisition_model_node.architecture" in source
    assert "k3s_acquisition_cluster.artifacts" in source
    assert "k3s_acquisition_cluster.version" in source
    assert "ansible.builtin.get_url:" in source
    assert "checksum: \"sha256:" in source
    assert "no_log: true" in source
    assert "get.k3s.io" not in source
    assert "shell:" not in source
    commands = [task["ansible.builtin.command"] for task in yaml.safe_load(source) if "ansible.builtin.command" in task]
    assert commands == [{"argv": ["{{ k3s_acquisition_binary_path }}", "--version"]}]


def test_acquisition_uses_only_an_action_scoped_proxy_environment() -> None:
    source = ROLE.read_text(encoding="utf-8")

    assert "k3s_acquisition_artifact.proxy_url" in source
    assert "k3s_acquisition_runtime_proxy" not in source
    assert "k3s_acquisition_runtime_secret_file" in source
    assert "k3s_protected_secret" in source
    assert "from_json" in source
    assert "credentials.username" in source
    assert "credentials.password" in source
    assert "https_proxy" in source
    assert "url_username" not in source
    assert "url_password" not in source
    assert "/etc/apt" not in source
    assert "git config" not in source
    assert "environment:" in source


def test_runtime_secret_path_is_the_only_acquisition_secret_input() -> None:
    defaults = yaml.safe_load(DEFAULTS.read_text(encoding="utf-8"))
    source = ROLE.read_text(encoding="utf-8")

    assert "k3s_acquisition_runtime_secret_file" in defaults
    assert "k3s_acquisition_credentials" not in source
    assert "lookup('env'" not in source
    assert "op read" not in source
    assert "set_fact:" in source
    assert "credential_ref" in source


def test_missing_checksum_fails_before_get_url(tmp_path: Path) -> None:
    playbook = tmp_path / "missing-checksum.yml"
    _write_role_playbook(
        playbook,
        {"url": "https://artifacts.synthetic.invalid/k3s/v1.35.1+k3s1/amd64/k3s"},
    )

    result = _run(playbook)

    assert result.returncode != 0
    assert "Acquire the exact pinned K3s executable" not in result.stdout


def test_non_https_url_fails_before_get_url(tmp_path: Path) -> None:
    playbook = tmp_path / "wrong-version.yml"
    _write_role_playbook(
        playbook,
        {
            "url": "http://artifacts.synthetic.invalid/k3s/v1.35.0+k3s1/amd64/k3s",
            "sha256": "a" * 64,
        },
    )

    result = _run(playbook)

    assert result.returncode != 0
    assert "Acquire the exact pinned K3s executable" not in result.stdout


def test_missing_auth_secret_fails_before_get_url(tmp_path: Path) -> None:
    playbook = tmp_path / "missing-secret.yml"
    _write_role_playbook(
        playbook,
        {
            "url": "https://artifacts.synthetic.invalid/k3s/v1.35.1+k3s1/amd64/k3s",
            "sha256": "a" * 64,
            "credential_ref": "op://synthetic/artifact-proxy/credentials",
        },
        k3s_acquisition_runtime_secret_file=str(tmp_path / "absent.json"),
    )

    result = _run(playbook)

    assert result.returncode != 0
    assert "k3s_protected_secret" in result.stdout + result.stderr
    assert "artifact-proxy" not in result.stdout + result.stderr


def test_auth_value_is_not_serialized_into_role_facts() -> None:
    source = ROLE.read_text(encoding="utf-8")

    assert "k3s_acquisition_credentials:" not in source
    registers = [task["register"] for task in yaml.safe_load(source) if "register" in task]
    assert registers == ["k3s_acquisition_observed_version"]
    assert "lookup('k3s_protected_secret'" in source
