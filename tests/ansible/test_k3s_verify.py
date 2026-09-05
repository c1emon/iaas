"""Offline synthetic coverage for read-only K3s bootstrap verification."""

from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[2]
ANSIBLE_DIR = ROOT / "automation" / "ansible"
PLAYBOOK = ANSIBLE_DIR / "playbooks" / "k3s" / "verify.yml"
ROLE_FILES = [
    ANSIBLE_DIR / "roles" / "k3s_verify" / "defaults" / "main.yml",
    ANSIBLE_DIR / "roles" / "k3s_verify" / "tasks" / "main.yml",
    ANSIBLE_DIR / "roles" / "k3s_verify" / "tasks" / "verify-node.yml",
]
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


def _nodes(*, ready: bool = True, reason: str = "", message: str = "") -> str:
    model = yaml.safe_load(MODEL.read_text(encoding="utf-8"))
    items: list[dict[str, Any]] = []
    for node in model["nodes"]:
        conditions: list[dict[str, str]] = [
            {
                "type": "Ready",
                "status": "True" if ready else "False",
                "reason": reason,
                "message": message,
            }
        ]
        labels = (
            {"node-role.kubernetes.io/control-plane": "true"}
            if node["role"] == "server"
            else {}
        )
        items.append(
            {
                "metadata": {"name": node["vm_ref"], "labels": labels},
                "status": {
                    "nodeInfo": {"kubeletVersion": model["cluster"]["version"]},
                    "conditions": conditions,
                },
            }
        )
    return json.dumps({"apiVersion": "v1", "items": items})


def _probe_outputs(*, ready: bool = True, reason: str = "", message: str = "") -> dict[str, Any]:
    return {
        "api": {"rc": 0, "stdout": "ok\n"},
        "nodes": {"rc": 0, "stdout": _nodes(ready=ready, reason=reason, message=message)},
        "etcd": {"rc": 0, "stdout": "[+]etcd ok\n"},
        "service": {"rc": 0, "stdout": "active\n"},
    }


def _inventory(tmp_path: Path, *, outputs: dict[str, Any] | None = None) -> Path:
    model = yaml.safe_load(MODEL.read_text(encoding="utf-8"))
    hosts: dict[str, dict[str, Any]] = {}
    for node in model["nodes"]:
        hosts[node["vm_ref"]] = {
            "ansible_connection": "local",
            "k3s_verify_command_outputs": outputs or _probe_outputs(),
        }
    path = tmp_path / "inventory.yml"
    path.write_text(yaml.safe_dump({"all": {"hosts": hosts}}, sort_keys=False), encoding="utf-8")
    return path


def _extra(scope: list[str] | None = None) -> list[str]:
    return [
        "-e",
        json.dumps(
            {
                "k3s_model_path": str(MODEL),
                "k3s_verify_scope": scope or [
                    "synthetic-server-01",
                    "synthetic-server-02",
                    "synthetic-server-03",
                    "synthetic-agent-01",
                ],
            }
        ),
    ]


def test_playbook_syntax_check_passes() -> None:
    result = _run(["-i", "localhost,", str(PLAYBOOK), "--syntax-check"])
    assert result.returncode == 0, result.stdout + result.stderr


def test_all_declared_nodes_and_services_pass_from_synthetic_outputs(tmp_path: Path) -> None:
    inventory = _inventory(tmp_path)
    result = _run(["-i", str(inventory), str(PLAYBOOK), *_extra()])
    assert result.returncode == 0, result.stdout + result.stderr
    assert "PASS verify.synthetic-server-01.registration" in result.stdout
    assert "PASS verify.synthetic-agent-01.service" in result.stdout
    assert "summary:" in result.stdout


def test_only_expected_cni_not_initialized_is_non_blocking(tmp_path: Path) -> None:
    inventory = _inventory(
        tmp_path,
        outputs=_probe_outputs(
            ready=False,
            reason="NetworkPluginNotReady",
            message="Network plugin returns error: cni plugin not initialized",
        ),
    )
    result = _run(["-i", str(inventory), str(PLAYBOOK), *_extra()])
    assert result.returncode == 0, result.stdout + result.stderr
    assert "WARN verify.synthetic-server-01.readiness" in result.stdout
    assert "fail" in result.stdout
    assert " 0 fail" in result.stdout


def test_other_readiness_failure_blocks(tmp_path: Path) -> None:
    inventory = _inventory(
        tmp_path,
        outputs=_probe_outputs(ready=False, reason="KubeletNotReady", message="kubelet stopped"),
    )
    result = _run(["-i", str(inventory), str(PLAYBOOK), *_extra()])
    assert result.returncode != 0
    assert "FAIL verify.synthetic-server-01.readiness" in result.stdout + result.stderr


def test_disk_pressure_is_not_hidden_by_cni_status(tmp_path: Path) -> None:
    outputs = _probe_outputs(
        ready=False,
        reason="NetworkPluginNotReady",
        message="cni plugin not initialized",
    )
    nodes = json.loads(outputs["nodes"]["stdout"])
    for item in nodes["items"]:
        item["status"]["conditions"].append({"type": "DiskPressure", "status": "True"})
    outputs["nodes"]["stdout"] = json.dumps(nodes)
    inventory = _inventory(tmp_path, outputs=outputs)
    result = _run(["-i", str(inventory), str(PLAYBOOK), *_extra()])
    assert result.returncode != 0
    assert "FAIL verify.synthetic-server-01.readiness" in result.stdout + result.stderr


def test_scope_must_be_explicit_and_declared(tmp_path: Path) -> None:
    inventory = _inventory(tmp_path)
    missing = _run(["-i", str(inventory), str(PLAYBOOK), "-e", json.dumps({"k3s_model_path": str(MODEL)})])
    assert missing.returncode != 0
    unknown = _run(["-i", str(inventory), str(PLAYBOOK), *_extra(["not-declared"])])
    assert unknown.returncode != 0
    assert "unknown" in unknown.stdout + unknown.stderr


def test_api_etcd_role_version_and_service_failures_block(tmp_path: Path) -> None:
    outputs = _probe_outputs()
    outputs["api"] = {"rc": 1, "stdout": "connection refused"}
    outputs["etcd"] = {"rc": 0, "stdout": "[+]etcd failed"}
    outputs["service"] = {"rc": 3, "stdout": "failed"}
    nodes = json.loads(outputs["nodes"]["stdout"])
    nodes["items"][0]["status"]["nodeInfo"]["kubeletVersion"] = "v0.0.0"
    outputs["nodes"]["stdout"] = json.dumps(nodes)
    inventory = _inventory(tmp_path, outputs=outputs)
    result = _run(["-i", str(inventory), str(PLAYBOOK), *_extra()])
    assert result.returncode != 0
    combined = result.stdout + result.stderr
    assert "FAIL verify.api" in combined
    assert "FAIL verify.etcd" in combined
    assert "FAIL verify.synthetic-server-01.version" in combined
    assert "FAIL verify.synthetic-server-01.service" in combined


def test_verification_path_has_no_mutation_modules_or_commands() -> None:
    source = "\n".join(path.read_text(encoding="utf-8") for path in [PLAYBOOK, *ROLE_FILES])
    assert "apt update" not in source
    assert not re.search(
        r"ansible\.builtin\.(apt|copy|template|file|lineinfile|blockinfile|replace|package|service|systemd|reboot)",
        source,
    )
    assert not re.search(
        r"\b(command|shell):\s*(apt|apt-get|systemctl\s+(start|stop|restart|enable|disable)|rm|mv|cp|tee|sed\s+-i|curl\s+.*-o|wget\s+.*-O)\b",
        source,
    )


def test_playbook_consumes_explicit_model_and_scope() -> None:
    source = PLAYBOOK.read_text(encoding="utf-8")
    assert "k3s_model_path" in source
    assert "k3s_verify_scope" in source
    assert "hosts: localhost" in source
