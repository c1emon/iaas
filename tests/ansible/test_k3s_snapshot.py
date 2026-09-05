"""Synthetic coverage for the explicit embedded-etcd snapshot workflow."""

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
PLAYBOOK = ANSIBLE_DIR / "playbooks" / "k3s" / "snapshot.yml"
ROLE_FILES = [
    ANSIBLE_DIR / "roles" / "k3s_snapshot" / "defaults" / "main.yml",
    ANSIBLE_DIR / "roles" / "k3s_snapshot" / "tasks" / "main.yml",
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


def _inventory(tmp_path: Path, *, outputs: dict[str, Any] | None = None) -> Path:
    model = yaml.safe_load(MODEL.read_text(encoding="utf-8"))
    hosts: dict[str, dict[str, Any]] = {}
    for node in model["nodes"]:
        host: dict[str, Any] = {"ansible_connection": "local"}
        if node["vm_ref"] == model["cluster"]["snapshot"]["source_vm_ref"] and outputs:
            host["k3s_snapshot_command_outputs"] = outputs
        hosts[node["vm_ref"]] = host
    path = tmp_path / "inventory.yml"
    path.write_text(
        yaml.safe_dump({"all": {"hosts": hosts}}, sort_keys=False),
        encoding="utf-8",
    )
    return path


def _outputs(
    *,
    api: str = "ok\n",
    etcd: str = "[+]etcd ok\n",
    service: str = "active\n",
    save_rc: int = 0,
) -> dict[str, Any]:
    return {
        "api": {"rc": 0 if api == "ok\n" else 1, "stdout": api},
        "etcd": {"rc": 0 if "etcd ok" in etcd else 1, "stdout": etcd},
        "service": {"rc": 0 if service == "active\n" else 3, "stdout": service},
        "save": {"rc": save_rc, "stdout": "snapshot created\n" if save_rc == 0 else "failed\n"},
    }


def _extra(scope: list[str] | None = None) -> list[str]:
    return [
        "-e",
        json.dumps(
            {
                "k3s_model_path": str(MODEL),
                "k3s_snapshot_scope": scope or ["synthetic-server-01"],
            }
        ),
    ]


def test_playbook_syntax_check_passes() -> None:
    result = _run(["-i", "localhost,", str(PLAYBOOK), "--syntax-check"])
    assert result.returncode == 0, result.stdout + result.stderr


def test_configured_source_server_snapshot_passes_with_redacted_metadata(tmp_path: Path) -> None:
    inventory = _inventory(tmp_path, outputs=_outputs())
    result = _run(["-i", str(inventory), str(PLAYBOOK), *_extra()])
    assert result.returncode == 0, result.stdout + result.stderr
    assert "PASS snapshot.synthetic-server-01" in result.stdout
    assert "k3s-synthetic-k3s-etcd" in result.stdout
    assert "/var/lib/rancher/k3s/server/db/snapshots" in result.stdout
    assert "snapshot created" not in result.stdout
    assert "restore readiness was not assessed" in result.stdout


def test_health_failure_blocks_snapshot_before_save(tmp_path: Path) -> None:
    inventory = _inventory(tmp_path, outputs=_outputs(etcd="[+]etcd failed\n"))
    result = _run(["-i", str(inventory), str(PLAYBOOK), *_extra()])
    assert result.returncode != 0
    combined = result.stdout + result.stderr
    assert "failed the read-only" in combined
    assert "PASS snapshot." not in combined


def test_save_failure_is_blocking(tmp_path: Path) -> None:
    inventory = _inventory(tmp_path, outputs=_outputs(save_rc=1))
    result = _run(["-i", str(inventory), str(PLAYBOOK), *_extra()])
    assert result.returncode != 0
    assert "snapshot creation failed" in result.stdout + result.stderr


def test_scope_must_be_exactly_the_declared_source_server(tmp_path: Path) -> None:
    inventory = _inventory(tmp_path, outputs=_outputs())
    unknown = _run(["-i", str(inventory), str(PLAYBOOK), *_extra(["synthetic-server-02"])])
    assert unknown.returncode != 0
    assert "exactly the configured" in unknown.stdout + unknown.stderr
    multiple = _run(
        [
            "-i",
            str(inventory),
            str(PLAYBOOK),
            *_extra(["synthetic-server-01", "synthetic-server-02"]),
        ]
    )
    assert multiple.returncode != 0


def test_workflow_has_no_copy_delete_restore_or_token_output_path() -> None:
    source = "\n".join(path.read_text(encoding="utf-8") for path in [PLAYBOOK, *ROLE_FILES])
    assert "k3s etcd-snapshot save" not in source
    assert "etcd-snapshot" in source
    assert not re.search(r"ansible\.builtin\.(fetch|synchronize|slurp)", source)
    assert not re.search(r"state:\s+absent|\b(command|shell):\s*(rm|mv|cp|tar)\b", source)
    assert "server_token" not in source
    assert "mode: \"0700\"" in source
    assert "owner: root" in source and "group: root" in source


def test_workflow_consumes_explicit_model_and_scope() -> None:
    source = PLAYBOOK.read_text(encoding="utf-8")
    assert "k3s_model_path" in source
    assert "k3s_snapshot_scope" in source
    assert "source_vm_ref" in source
    assert "hosts: localhost" in source
