"""Synthetic and static coverage for the serial K3s upgrade orchestration."""

from __future__ import annotations

import os
import json
import subprocess
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[2]
ANSIBLE_DIR = ROOT / "automation" / "ansible"
PLAYBOOK = ANSIBLE_DIR / "playbooks" / "k3s" / "upgrade.yml"
ROLE_DIR = ANSIBLE_DIR / "roles" / "k3s_upgrade"
MODEL = ROOT / "tests" / "fixtures" / "k3s" / "expected-review.yml"


def _run(args: list[str]) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["ANSIBLE_CONFIG"] = str(ANSIBLE_DIR / "ansible.cfg")
    return subprocess.run(
        ["uv", "run", "ansible-playbook", *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )


def _role_playbook(path: Path, *, result: dict[str, Any]) -> None:
    model = yaml.safe_load(MODEL.read_text(encoding="utf-8"))
    path.write_text(
        yaml.safe_dump(
            [
                {
                    "hosts": model["nodes"][0]["vm_ref"],
                    "gather_facts": False,
                    "connection": "local",
                    "vars": {
                        "k3s_upgrade_model": model,
                        "k3s_upgrade_node": model["nodes"][0],
                        "k3s_upgrade_target_version": model["cluster"]["version"],
                        "k3s_upgrade_observed_version": "v1.35.1+k3s1",
                        "k3s_upgrade_skip": True,
                        "k3s_upgrade_synthetic": True,
                        "k3s_upgrade_synthetic_result": result,
                    },
                    "roles": ["k3s_upgrade"],
                }
            ],
            sort_keys=False,
        ),
        encoding="utf-8",
    )


def test_upgrade_playbook_syntax_check_passes() -> None:
    result = _run(["-i", "localhost,", str(PLAYBOOK), "--syntax-check"])
    assert result.returncode == 0, result.stdout + result.stderr


def test_synthetic_exact_target_is_health_checked_and_skipped(tmp_path: Path) -> None:
    playbook = tmp_path / "upgrade-role.yml"
    _role_playbook(playbook, result={"pre_health_rc": 0, "pre_health_stdout": "ok"})
    result = _run(["-i", "synthetic-server-01,", str(playbook)])
    assert result.returncode == 0, result.stdout + result.stderr
    assert "SKIP upgrade.synthetic-server-01" in result.stdout


def test_synthetic_stop_failure_blocks_before_acquisition(tmp_path: Path) -> None:
    playbook = tmp_path / "upgrade-role.yml"
    _role_playbook(playbook, result={"pre_health_rc": 0, "pre_health_stdout": "ok", "stop_rc": 1})
    # The role is intentionally run as a mutation candidate for this case.
    source = yaml.safe_load(playbook.read_text(encoding="utf-8"))
    source[0]["vars"]["k3s_upgrade_skip"] = False
    playbook.write_text(yaml.safe_dump(source, sort_keys=False), encoding="utf-8")
    result = _run(["-i", "synthetic-server-01,", str(playbook)])
    assert result.returncode != 0
    assert "service stop failed" in result.stdout + result.stderr


def test_full_synthetic_upgrade_runs_preflight_snapshot_and_server_then_agents(tmp_path: Path) -> None:
    model = yaml.safe_load(MODEL.read_text(encoding="utf-8"))
    target = model["cluster"]["version"]
    refs = [node["vm_ref"] for node in model["nodes"]]
    facts = {
        "os_family": "Debian",
        "distribution": "Debian",
        "architecture": "x86_64",
        "pve_architecture": "amd64",
        "cgroups_v2": True,
        "kernel_capabilities": ["NET_ADMIN", "SYS_ADMIN"],
        "time_synchronized": True,
        "node_ip": "198.51.100.11",
        "node_interface": "cluster0",
        "ports_available": True,
        "free_bytes": 50 * 1024**3,
        "apt_sources_reachable": True,
        "artifact_reachable": True,
        "registry_reachable": True,
        "registry_tls_files_valid": True,
        "conflicting_install_state": False,
    }
    hosts: dict[str, dict[str, Any]] = {}
    for node in model["nodes"]:
        host: dict[str, Any] = {
            "ansible_connection": "local",
            "k3s_preflight_facts": {**facts, "node_ip": node["node_ip"]},
            "k3s_preflight_credentials": True,
            "k3s_upgrade_synthetic_result": {
                "pre_health_stdout": "active" if node["role"] == "agent" else "ok",
                "post_nodes_stdout": node["vm_ref"],
                "post_service_stdout": "active",
            },
        }
        if node["vm_ref"] == model["cluster"]["snapshot"]["source_vm_ref"]:
            host["k3s_snapshot_command_outputs"] = {
                "api": {"rc": 0, "stdout": "ok\n"},
                "etcd": {"rc": 0, "stdout": "[+]etcd ok\n"},
                "service": {"rc": 0, "stdout": "active\n"},
                "save": {"rc": 0, "stdout": "snapshot created\n"},
            }
        hosts[node["vm_ref"]] = host
    inventory = tmp_path / "inventory.yml"
    inventory.write_text(yaml.safe_dump({"all": {"hosts": hosts}}, sort_keys=False), encoding="utf-8")
    extra = {
        "k3s_upgrade_model_path": str(MODEL),
        "k3s_upgrade_scope": refs,
        "k3s_upgrade_target_version": target,
        "k3s_upgrade_observed_versions": {ref: "v1.34.0+k3s1" for ref in refs},
        "k3s_upgrade_plan": {
            "scope": refs,
            "target_version": target,
            "skipped": [],
            "to_upgrade": refs,
        },
        "k3s_upgrade_synthetic": True,
    }
    result = _run(["-i", str(inventory), str(PLAYBOOK), "-e", json.dumps(extra)])
    assert result.returncode == 0, result.stdout + result.stderr
    output = result.stdout
    assert "PASS snapshot.synthetic-server-01" in output
    assert output.index("Run the serial server upgrade stage") < output.index("Run the serial agent upgrade stage")


def test_upgrade_orchestration_is_explicit_serial_and_fail_closed() -> None:
    source = PLAYBOOK.read_text(encoding="utf-8")
    assert "import_playbook: preflight.yml" in source
    assert "import_playbook: snapshot.yml" in source
    assert "k3s_preflight_scope" in source
    assert "k3s_snapshot_scope" in source
    assert "k3s_snapshot_source_vm_ref" in source
    assert source.count("serial: 1") == 2
    assert source.count("any_errors_fatal: true") == 2
    assert "must explicitly name every declared node" in source
    assert "k3s_upgrade_scope: []" in source
    assert "hosts: all" in source


def test_upgrade_role_does_not_expose_destructive_recovery_operations() -> None:
    source = "\n".join(path.read_text(encoding="utf-8") for path in ROLE_DIR.rglob("*") if path.is_file())
    assert "restore" not in source.lower()
    assert "uninstall" not in source.lower()
    assert "remove node" not in source.lower()
    assert "no_log: true" in source
