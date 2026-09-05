"""Exercise the VM-baseline runtime secret lookup without exposing its value."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ANSIBLE_DIR = ROOT / "automation" / "ansible"
REFERENCE = "op://synthetic/vm-baseline/apt-proxy"
SECRET = "synthetic-vm-baseline-proxy-secret"


def _run_lookup(secret_file: Path, expression: str) -> subprocess.CompletedProcess[str]:
    playbook = secret_file.parent / "lookup.yml"
    playbook.write_text(
        """---
- hosts: localhost
  gather_facts: false
  connection: local
  tasks:
    - name: Resolve a protected value only for this redacted assertion
      ansible.builtin.assert:
        that:
          - """
        + expression
        + """
      no_log: true
      changed_when: false
""",
        encoding="utf-8",
    )
    environment = os.environ.copy()
    environment["ANSIBLE_CONFIG"] = str(ANSIBLE_DIR / "ansible.cfg")
    return subprocess.run(
        ["uv", "run", "ansible-playbook", "-i", "localhost,", str(playbook)],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )


def test_lookup_reads_only_a_protected_explicit_file_inside_no_log_task(
    tmp_path: Path,
) -> None:
    secret_file = tmp_path / "runtime.json"
    secret_file.write_text(json.dumps({REFERENCE: SECRET}), encoding="utf-8")
    secret_file.chmod(0o600)

    result = _run_lookup(
        secret_file,
        "lookup('vm_baseline_protected_secret', '" + REFERENCE + "', secret_file='"
        + str(secret_file)
        + "') | length > 0",
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert SECRET not in result.stdout + result.stderr


def test_lookup_rejects_unprotected_file_without_secret_output(tmp_path: Path) -> None:
    secret_file = tmp_path / "runtime.json"
    secret_file.write_text(json.dumps({REFERENCE: SECRET}), encoding="utf-8")
    secret_file.chmod(0o644)

    result = _run_lookup(
        secret_file,
        "lookup('vm_baseline_protected_secret', '" + REFERENCE + "', secret_file='"
        + str(secret_file)
        + "') | length > 0",
    )

    assert result.returncode != 0
    assert SECRET not in result.stdout + result.stderr


def test_lookup_requires_explicit_file_and_does_not_use_environment() -> None:
    source = (
        ANSIBLE_DIR / "plugins" / "lookup" / "vm_baseline_protected_secret.py"
    ).read_text(encoding="utf-8")

    assert "load_protected_environment_json" in source
    assert "secret_file" in source
    assert "os.environ" not in source
    assert "subprocess" not in source
