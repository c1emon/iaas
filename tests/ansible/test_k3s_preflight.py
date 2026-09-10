"""Offline synthetic coverage for the read-only K3s preflight playbook."""

from __future__ import annotations

import os
import json
import re
import subprocess
from pathlib import Path
from typing import Any

import yaml
import pytest


ROOT = Path(__file__).resolve().parents[2]
ANSIBLE_DIR = ROOT / "automation" / "ansible"
PLAYBOOK = ANSIBLE_DIR / "playbooks" / "k3s" / "preflight.yml"
ROLE_TASKS = ANSIBLE_DIR / "roles" / "k3s_preflight" / "tasks" / "main.yml"
MODEL = ROOT / "tests" / "fixtures" / "k3s" / "expected-review.yml"


def _run(args: list[str], *, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    merged = os.environ.copy()
    merged["ANSIBLE_CONFIG"] = str(ANSIBLE_DIR / "ansible.cfg")
    if env:
        merged.update(env)
    return subprocess.run(
        ["uv", "run", "ansible-playbook", *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        env=merged,
        check=False,
    )


def _write_inventory(path: Path, hosts: dict[str, dict[str, Any]]) -> None:
    path.write_text(
        yaml.safe_dump({"all": {"hosts": hosts}}, sort_keys=False),
        encoding="utf-8",
    )


def _facts(**overrides: Any) -> dict[str, Any]:
    facts: dict[str, Any] = {
        "os_family": "Debian",
        "distribution": "Debian",
        "distribution_major_version": "12",
        "architecture": "x86_64",
        "pve_architecture": "amd64",
        "cgroups_v2": True,
        "kernel_capabilities": ["NET_ADMIN", "SYS_ADMIN"],
        "time_synchronized": True,
        "node_ip": "198.51.100.11",
        "node_interface": "cluster0",
        "listening_ports": [6443, 6444, 10250],
        "ports_available": True,
        "free_bytes": 50 * 1024**3,
        "apt_sources_reachable": True,
        "artifact_reachable": True,
        "registry_reachable": True,
        "registry_tls_files_valid": True,
        "installation": {"state": "fresh"},
    }
    facts.update(overrides)
    return facts


def _host(name: str = "synthetic-server-01", **facts: Any) -> dict[str, Any]:
    return {
        "ansible_connection": "local",
        "ansible_host": "127.0.0.1",
        "ansible_user": "ops",
        "k3s_preflight_facts": _facts(**facts),
        "k3s_preflight_credentials": True,
        "k3s_node_ip": "198.51.100.11",
        "k3s_preflight_model_node": name,
    }


def _extra(scope: list[str] | None = None) -> list[str]:
    return [
        "-e",
        json.dumps(
            {
                "k3s_model_path": str(MODEL),
                "k3s_preflight_scope": scope or ["synthetic-server-01"],
                "k3s_preflight_mode": "install",
            }
        ),
    ]


def test_playbook_syntax_check_passes() -> None:
    result = _run(["-i", "localhost,", str(PLAYBOOK), "--syntax-check"])
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize("mode,deploy,upgrade", [("", "", ""), ("wrong", "", ""),
                                                ("install", "model.yml", ""), ("converge", "", "model.yml")])
def test_mode_rejection_precedes_model_or_host_access(mode, deploy, upgrade):
    result = _run(["-i", "localhost,", str(PLAYBOOK), "-e", json.dumps({
        "k3s_preflight_mode": mode, "k3s_deploy_model_path": deploy, "k3s_upgrade_model_path": upgrade})])
    assert result.returncode != 0
    assert "without a policy override" in result.stdout
    assert "Load the validated" not in result.stdout


@pytest.mark.parametrize("mode,version,valid", [("converge", "v1.35.1+k3s1", True),
                                              ("upgrade", "v1.34.0+k3s1", True),
                                              ("converge", "v1.34.0+k3s1", False)])
def test_installed_cluster_uses_operation_policy(tmp_path, mode, version, valid):
    model = yaml.safe_load(MODEL.read_text())
    node = model["nodes"][0]
    inventory = tmp_path / "installed.yml"
    _write_inventory(inventory, {node["vm_ref"]: _host(ports_available=False, installation={
        "state": "managed", "version": version, "sha256": model["cluster"]["artifacts"][node["architecture"]]["sha256"],
        "service_active": True, "datastore": True})})
    result = _run(["-i", str(inventory), str(PLAYBOOK), *_extra(), "-e", json.dumps({"k3s_preflight_mode": mode})])
    assert (result.returncode == 0) == valid, result.stdout + result.stderr


def test_no_hosts_is_reported_without_remote_access(tmp_path: Path) -> None:
    inventory = tmp_path / "empty.yml"
    _write_inventory(inventory, {})
    result = _run(["-i", str(inventory), str(PLAYBOOK), *_extra()])
    assert result.returncode == 0, result.stdout + result.stderr
    assert "SKIP" in result.stdout
    assert "summary:" in result.stdout


def test_prepared_synthetic_host_passes(tmp_path: Path) -> None:
    inventory = tmp_path / "inventory.yml"
    _write_inventory(inventory, {"synthetic-server-01": _host()})
    result = _run(["-i", str(inventory), str(PLAYBOOK), *_extra()])
    assert result.returncode == 0, result.stdout + result.stderr
    assert "PASS preflight.synthetic-server-01.os" in result.stdout
    assert "summary:" in result.stdout


def test_unreachable_host_is_a_warning_and_does_not_mutate(tmp_path: Path) -> None:
    inventory = tmp_path / "inventory.yml"
    _write_inventory(
        inventory,
        {"synthetic-server-01": {"ansible_connection": "ssh", "ansible_host": "192.0.2.11", "ansible_user": "ops"}},
    )
    result = _run(["-i", str(inventory), str(PLAYBOOK), *_extra()], env={"ANSIBLE_HOST_KEY_CHECKING": "False"})
    assert result.returncode == 0, result.stdout + result.stderr
    assert "WARN ssh.synthetic-server-01.reachability" in result.stdout


def test_warning_is_reported_but_is_non_blocking(tmp_path: Path) -> None:
    inventory = tmp_path / "inventory.yml"
    _write_inventory(inventory, {"synthetic-server-01": _host(time_synchronized=False)})
    result = _run(["-i", str(inventory), str(PLAYBOOK), *_extra()])
    assert result.returncode == 0, result.stdout + result.stderr
    assert "WARN preflight.synthetic-server-01.time" in result.stdout


def test_missing_action_scoped_credentials_fail_before_endpoint_checks(tmp_path: Path) -> None:
    inventory = tmp_path / "inventory.yml"
    host = _host()
    host["k3s_preflight_credentials"] = False
    _write_inventory(inventory, {"synthetic-server-01": host})
    result = _run(["-i", str(inventory), str(PLAYBOOK), *_extra()])
    assert result.returncode != 0
    assert "action-scoped" in result.stdout + result.stderr


def test_blocking_failure_stops_preflight(tmp_path: Path) -> None:
    inventory = tmp_path / "inventory.yml"
    _write_inventory(inventory, {"synthetic-server-01": _host(os_family="RedHat")})
    result = _run(["-i", str(inventory), str(PLAYBOOK), *_extra()])
    assert result.returncode != 0
    assert "FAIL preflight.synthetic-server-01.os" in result.stdout + result.stderr


def test_preflight_path_contains_no_mutation_modules_or_commands() -> None:
    source = "\n".join(path.read_text(encoding="utf-8") for path in [PLAYBOOK, ROLE_TASKS])
    assert "apt update" not in source
    assert "ansible.builtin.apt" not in source
    assert not re.search(r"^\s+ansible\.builtin\.(copy|template|file|lineinfile|blockinfile|replace|package|service|systemd):", source, re.M)
    assert not re.search(r"\b(command|shell):\s*(apt|apt-get|systemctl|service|rm|mv|cp|tee|sed\s+-i|curl\s+.*-o|wget\s+.*-O)\b", source)


def test_preflight_path_probes_declared_endpoints_and_tls_read_only() -> None:
    source = ROLE_TASKS.read_text(encoding="utf-8")
    assert "ansible.builtin.uri" in source
    assert "k3s_preflight_artifact.url" in source
    assert "k3s_preflight_artifact.proxy_url" in source
    assert "k3s_preflight_registry_mirrors" in source
    assert "ansible.builtin.stat" in source
    assert "k3s_preflight_runtime_secret_file" in source
    assert "k3s_protected_secret" in source
    assert "URIs:" in source
    assert "apt update" not in source


def test_model_consumption_and_explicit_scope_are_visible() -> None:
    source = PLAYBOOK.read_text(encoding="utf-8")
    assert "k3s_model_path" in source
    assert "k3s_preflight_scope" in source
    assert "k3s.intent" not in source
    assert "hosts: localhost" in source
