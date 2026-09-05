"""Exercise the runtime secret lookup without exposing its synthetic value."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ANSIBLE_DIR = ROOT / "automation" / "ansible"
REFERENCE = "op://synthetic/k3s/lookup-token"


def test_lookup_reads_only_a_protected_explicit_file_inside_no_log_task(tmp_path: Path) -> None:
    secret_file = tmp_path / "runtime.json"
    secret_file.write_text(json.dumps({REFERENCE: "synthetic-lookup-value"}), encoding="utf-8")
    secret_file.chmod(0o600)
    playbook = tmp_path / "lookup.yml"
    playbook.write_text(
        """---
- hosts: localhost
  gather_facts: false
  connection: local
  tasks:
    - name: Resolve a protected value only for this redacted assertion
      ansible.builtin.assert:
        that:
          - lookup('k3s_protected_secret', 'op://synthetic/k3s/lookup-token', secret_file='"""
        + str(secret_file)
        + """') == 'synthetic-lookup-value'
      no_log: true
      changed_when: false
""",
        encoding="utf-8",
    )
    environment = os.environ.copy()
    environment["ANSIBLE_CONFIG"] = str(ANSIBLE_DIR / "ansible.cfg")
    result = subprocess.run(
        ["uv", "run", "ansible-playbook", "-i", "localhost,", str(playbook)],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "synthetic-lookup-value" not in result.stdout + result.stderr


def test_lookup_source_uses_shared_channel_and_does_not_fall_back_to_environment() -> None:
    source = (ANSIBLE_DIR / "plugins" / "lookup" / "k3s_protected_secret.py").read_text(
        encoding="utf-8"
    )

    assert "load_protected_environment_json" in source
    assert "os.environ" not in source
    assert "subprocess" not in source
