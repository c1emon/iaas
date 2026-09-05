"""Synthetic coverage for the K3s runtime configuration role."""

from __future__ import annotations

import os
import getpass
import subprocess
from pathlib import Path
import yaml


ROOT = Path(__file__).resolve().parents[2]
ANSIBLE_DIR = ROOT / "automation" / "ansible"
ROLE_DIR = ANSIBLE_DIR / "roles" / "k3s_runtime_config"
MODEL = ROOT / "tests" / "fixtures" / "k3s" / "expected-review.yml"


def _run(args: list[str]) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment["ANSIBLE_CONFIG"] = str(ANSIBLE_DIR / "ansible.cfg")
    return subprocess.run(
        ["uv", "run", "ansible-playbook", *args],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )


def _playbook(path: Path, output_dir: Path) -> None:
    model = yaml.safe_load(MODEL.read_text(encoding="utf-8"))
    path.write_text(
        yaml.safe_dump(
            [{
                "hosts": "localhost",
                "gather_facts": False,
                "connection": "local",
                "vars": {
                    "k3s_runtime_model": model,
                    "k3s_runtime_node": model["nodes"][0],
                    "k3s_runtime_restart_services": False,
                    "k3s_runtime_owner": getpass.getuser(),
                    "k3s_runtime_group": "staff",
                    "k3s_runtime_config_dir": str(output_dir),
                    "k3s_runtime_config_path": str(output_dir / "config.yaml"),
                    "k3s_runtime_registries_path": str(output_dir / "registries.yaml"),
                    "k3s_runtime_service_env_path": str(output_dir / "k3s.service.env"),
                    "k3s_runtime_registry_credentials": {
                        "op://synthetic/registry/credentials": {
                            "username": "synthetic-user",
                            "password": "synthetic-password",
                        }
                    },
                    "k3s_runtime_proxy_credentials": {
                        "op://synthetic/service-proxy/credentials": {
                            "username": "proxy-user",
                            "password": "proxy-password",
                        }
                    },
                    "k3s_runtime_tls_files": {
                        "op://synthetic/registry/ca-pem": "/etc/k3s/ca.pem",
                        "op://synthetic/registry/client-cert-pem": "/etc/k3s/client.crt",
                        "op://synthetic/registry/client-key-pem": "/etc/k3s/client.key",
                    },
                },
                "roles": ["k3s_runtime_config"],
            }],
            sort_keys=False,
        ),
        encoding="utf-8",
    )


def test_role_has_valid_ansible_syntax(tmp_path: Path) -> None:
    playbook = tmp_path / "runtime.yml"
    _playbook(playbook, tmp_path / "rendered")
    result = _run(["-i", "localhost,", str(playbook), "--syntax-check"])
    assert result.returncode == 0, result.stdout + result.stderr


def test_role_renders_model_policy_and_runtime_values(tmp_path: Path) -> None:
    output_dir = tmp_path / "rendered"
    playbook = tmp_path / "runtime.yml"
    _playbook(playbook, output_dir)
    result = _run(["-i", "localhost,", str(playbook)])
    assert result.returncode == 0, result.stdout + result.stderr

    config = (output_dir / "config.yaml").read_text(encoding="utf-8")
    registries = (output_dir / "registries.yaml").read_text(encoding="utf-8")
    environment = (output_dir / "k3s.service.env").read_text(encoding="utf-8")
    assert 'node-ip: "198.51.100.11"' in config
    assert "flannel-backend: none" in config
    assert "disable-default-registry-endpoint: true" in config
    assert '"https://registry.synthetic.invalid"' in registries
    assert '"synthetic-user"' in registries
    assert '"synthetic-password"' in registries
    assert "proxy-user" in environment and "proxy-password" in environment
    assert "198.51.100.0/24" in environment


def test_role_is_redacted_and_owns_only_runtime_files() -> None:
    source = "\n".join(path.read_text(encoding="utf-8") for path in ROLE_DIR.rglob("*") if path.is_file())
    assert "no_log: true" in source
    assert "diff: false" in source
    assert "op read" not in source
    assert "ansible.builtin.apt" not in source
    assert "ansible.builtin.command" not in source
    assert "/etc/rancher/k3s/registries.yaml" in source
    assert "/etc/systemd/system/k3s.service.env" in source
    assert "/etc/systemd/system/k3s-agent.service.env" in source
