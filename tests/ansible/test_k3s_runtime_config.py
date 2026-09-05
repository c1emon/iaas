"""Synthetic coverage for the K3s runtime configuration role."""

from __future__ import annotations

import os
import getpass
import json
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


def _playbook(
    path: Path,
    output_dir: Path,
    secret_file: Path,
    state: str = "present",
    join_token: str = "",
) -> None:
    model = yaml.safe_load(MODEL.read_text(encoding="utf-8"))
    tls_dir = output_dir / "tls"
    tls_dir.mkdir(parents=True, exist_ok=True)
    tls_paths = {
        "op://synthetic/registry/ca-pem": tls_dir / "ca.pem",
        "op://synthetic/registry/client-cert-pem": tls_dir / "client.crt",
        "op://synthetic/registry/client-key-pem": tls_dir / "client.key",
    }
    for tls_path in tls_paths.values():
        tls_path.write_text("synthetic tls material\n", encoding="utf-8")
        tls_path.chmod(0o600)
    secret_file.write_text(
        json.dumps(
            {
                "op://synthetic/registry/credentials": json.dumps(
                    {"username": "synthetic-user", "password": "synthetic-password"}
                ),
                "op://synthetic/service-proxy/credentials": json.dumps(
                    {"username": "proxy-user", "password": "proxy-password"}
                ),
                **{reference: str(tls_path) for reference, tls_path in tls_paths.items()},
            }
        ),
        encoding="utf-8",
    )
    secret_file.chmod(0o600)
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
                    "k3s_runtime_state": state,
                    "k3s_runtime_secret_file": str(secret_file),
                    "k3s_runtime_join_token": join_token,
                    "k3s_runtime_owner": getpass.getuser(),
                    "k3s_runtime_group": "staff",
                    "k3s_runtime_config_dir": str(output_dir),
                    "k3s_runtime_config_path": str(output_dir / "config.yaml"),
                    "k3s_runtime_registries_path": str(output_dir / "registries.yaml"),
                    "k3s_runtime_service_env_path": str(output_dir / "k3s.service.env"),
                },
                "roles": ["k3s_runtime_config"],
            }],
            sort_keys=False,
        ),
        encoding="utf-8",
    )


def test_role_has_valid_ansible_syntax(tmp_path: Path) -> None:
    playbook = tmp_path / "runtime.yml"
    _playbook(playbook, tmp_path / "rendered", tmp_path / "runtime-secrets.json")
    result = _run(["-i", "localhost,", str(playbook), "--syntax-check"])
    assert result.returncode == 0, result.stdout + result.stderr


def test_role_renders_model_policy_and_runtime_values(tmp_path: Path) -> None:
    output_dir = tmp_path / "rendered"
    playbook = tmp_path / "runtime.yml"
    _playbook(playbook, output_dir, tmp_path / "runtime-secrets.json")
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


def test_join_token_is_rendered_only_in_the_restrictive_no_log_runtime_file(tmp_path: Path) -> None:
    output_dir = tmp_path / "rendered"
    playbook = tmp_path / "runtime.yml"
    join_token = "K10synthetic::synthetic-credential"
    _playbook(
        playbook,
        output_dir,
        tmp_path / "runtime-secrets.json",
        join_token=join_token,
    )
    result = _run(["-i", "localhost,", str(playbook)])

    assert result.returncode == 0, result.stdout + result.stderr
    assert join_token not in result.stdout + result.stderr
    config_path = output_dir / "config.yaml"
    assert f'token: "{join_token}"' in config_path.read_text(encoding="utf-8")
    assert config_path.stat().st_mode & 0o777 == 0o600


def test_unchanged_runtime_policy_is_idempotent(tmp_path: Path) -> None:
    output_dir = tmp_path / "rendered"
    playbook = tmp_path / "runtime.yml"
    _playbook(playbook, output_dir, tmp_path / "runtime-secrets.json")
    assert _run(["-i", "localhost,", str(playbook)]).returncode == 0
    result = _run(["-i", "localhost,", str(playbook)])
    assert result.returncode == 0, result.stdout + result.stderr
    assert "changed=0" in result.stdout
    assert "RUNNING HANDLER" not in result.stdout


def test_role_rejects_missing_or_world_readable_tls_files(tmp_path: Path) -> None:
    output_dir = tmp_path / "rendered"
    secret_file = tmp_path / "runtime-secrets.json"
    playbook = tmp_path / "runtime.yml"
    _playbook(playbook, output_dir, secret_file)
    (output_dir / "tls" / "ca.pem").unlink()
    result = _run(["-i", "localhost,", str(playbook)])
    assert result.returncode != 0

    _playbook(playbook, output_dir, secret_file)
    (output_dir / "tls" / "ca.pem").chmod(0o644)
    result = _run(["-i", "localhost,", str(playbook)])
    assert result.returncode != 0


def test_role_retirement_removes_only_its_owned_files(tmp_path: Path) -> None:
    output_dir = tmp_path / "rendered"
    secret_file = tmp_path / "runtime-secrets.json"
    playbook = tmp_path / "runtime.yml"
    _playbook(playbook, output_dir, secret_file)
    assert _run(["-i", "localhost,", str(playbook)]).returncode == 0
    unmanaged = output_dir / "unmanaged.conf"
    unmanaged.write_text("must survive\n", encoding="utf-8")

    _playbook(playbook, output_dir, secret_file, state="absent")
    result = _run(["-i", "localhost,", str(playbook)])
    assert result.returncode == 0, result.stdout + result.stderr
    assert not (output_dir / "config.yaml").exists()
    assert not (output_dir / "registries.yaml").exists()
    assert not (output_dir / "k3s.service.env").exists()
    assert unmanaged.exists()


def test_role_is_redacted_and_owns_only_runtime_files() -> None:
    source = "\n".join(path.read_text(encoding="utf-8") for path in ROLE_DIR.rglob("*") if path.is_file())
    tasks = (ROLE_DIR / "tasks" / "main.yml").read_text(encoding="utf-8")
    assert "no_log: true" in source
    assert "diff: false" in source
    assert "k3s_protected_secret" in source
    assert "k3s_runtime_registry_credentials" not in source
    assert "k3s_runtime_proxy_credentials" not in source
    assert "k3s_runtime_tls_files" not in source
    assert "op read" not in source
    assert "ansible.builtin.apt" not in source
    assert "ansible.builtin.command" not in tasks
    assert "/etc/rancher/k3s/registries.yaml" in source
    assert "/etc/systemd/system/k3s.service.env" in source
    assert "/etc/systemd/system/k3s-agent.service.env" in source


def test_restart_handler_has_a_health_gate_and_is_change_driven() -> None:
    tasks = (ROLE_DIR / "tasks" / "main.yml").read_text(encoding="utf-8")
    handler = (ROLE_DIR / "handlers" / "main.yml").read_text(encoding="utf-8")
    assert tasks.count("notify: Restart K3s runtime service") == 4
    assert "state: absent" in tasks
    assert "systemctl" in handler and "is-active" in handler
    assert "Require healthy K3s runtime after restart" in handler
    assert "k3s_runtime_restart_services | bool" in handler
