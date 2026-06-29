"""Offline checks for the canonical PVE guest verification playbook."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[2]
ANSIBLE_DIR = ROOT / "ansible"
PLAYBOOK = ANSIBLE_DIR / "playbooks" / "pve" / "verify-guests.yml"
TASKS_FILE = ANSIBLE_DIR / "playbooks" / "pve" / "tasks" / "verify-guest.yml"
ROOT_MAKEFILE = ROOT / "Makefile"
MODULE_MAKEFILE = ROOT / "infra" / "tofu" / "pve" / "Makefile"


def _run_ansible(args: list[str], *, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    command = ["uv", "run", "ansible-playbook", *args]
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)
    return subprocess.run(command, cwd=ROOT, capture_output=True, text=True, env=merged_env, check=False)


def _write_inventory(path: Path, hosts: dict[str, dict[str, Any]]) -> None:
    doc = {
        "all": {
            "children": {
                "pve_vms": {"hosts": hosts},
                "dev": {"hosts": {name: {} for name, host in hosts.items() if "dev" in host.get("pve_tags", [])}},
                "web": {"hosts": {name: {} for name, host in hosts.items() if "web" in host.get("pve_tags", [])}},
            }
        }
    }
    path.write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")


def _base_hostvars() -> dict[str, Any]:
    return {
        "ansible_host": "10.10.0.20",
        "ansible_user": "ops",
        "ansible_connection": "ssh",
        "ansible_become": False,
        "ansible_become_method": "sudo",
        "pve_ansible_groups": ["dev", "web"],
        "pve_tags": ["dev", "web"],
        "pve_dns": ["10.10.0.254"],
    }


def test_make_targets_and_playbook_are_ansible_first() -> None:
    root_make = ROOT_MAKEFILE.read_text(encoding="utf-8")
    module_make = MODULE_MAKEFILE.read_text(encoding="utf-8")
    playbook = PLAYBOOK.read_text(encoding="utf-8")
    tasks_file = TASKS_FILE.read_text(encoding="utf-8")

    assert "pve-verify-guests:" in root_make
    assert "$(MAKE) -C \"$(PVE_DIR)\" verify-guests" in root_make
    assert "pve-ansible-check:" in root_make and "$(MAKE) pve-verify-guests" in root_make
    assert "python -m scripts.pve_inventory.guest_verification" not in root_make

    assert "verify-guests:" in module_make
    assert "ansible-playbook -i \"$(ANSIBLE_INVENTORY)\" \"$(ANSIBLE_PLAYBOOK)\"" in module_make
    assert "verify-guests-syntax:" in module_make
    assert "--syntax-check" in module_make

    assert "hosts: localhost" in playbook
    assert "pve_guest_group: pve_vms" in playbook
    assert "python -m scripts.pve_inventory.guest_verification" not in playbook
    assert "ansible.builtin.setup:" in tasks_file
    assert "ansible.builtin.service_facts:" in tasks_file
    assert "ansible.builtin.slurp:" in tasks_file
    assert "ansible.builtin.command: sudo -n true" in tasks_file
    assert "ansible.builtin.command: sudo -n /usr/sbin/sshd -T" in tasks_file
    assert "ansible_hostname" in tasks_file
    assert "ansible_all_ipv4_addresses" in tasks_file
    assert "python3" not in tasks_file
    assert "from_json" not in tasks_file
    for secret_marker in ("IdentityFile", "id_rsa", "BEGIN OPENSSH PRIVATE KEY"):
        assert secret_marker not in (playbook + tasks_file)


def test_playbook_syntax_check_passes() -> None:
    result = _run_ansible(["-i", str(ANSIBLE_DIR / "inventories" / "generated" / "pve.yml"), str(PLAYBOOK), "--syntax-check"])
    assert result.returncode == 0, result.stdout + result.stderr


def test_no_guests_reports_skip_and_exits_zero(tmp_path: Path) -> None:
    inventory = tmp_path / "inventory.yml"
    _write_inventory(inventory, {})

    result = _run_ansible(["-i", str(inventory), str(PLAYBOOK)])

    assert result.returncode == 0, result.stdout + result.stderr
    assert "SKIP inventory.pve_vms: no declared guests found" in result.stdout
    assert "summary: 0 pass, 0 warn, 0 fail, 0 skip" in result.stdout


def test_unreachable_guest_reports_warn_and_continues(tmp_path: Path) -> None:
    inventory = tmp_path / "inventory.yml"
    _write_inventory(inventory, {"dev-web-01": _base_hostvars()})

    ssh_dir = tmp_path / "bin"
    ssh_dir.mkdir()
    ssh_log = tmp_path / "ssh-argv.txt"
    ssh_script = ssh_dir / "ssh"
    ssh_script.write_text(
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        "printf '%s\\n' \"$@\" > \"${SSH_CAPTURE}\"\n"
        "printf 'Permission denied (publickey).\\n' >&2\n"
        "exit 255\n",
        encoding="utf-8",
    )
    ssh_script.chmod(0o755)

    result = _run_ansible(
        ["-i", str(inventory), str(PLAYBOOK)],
        env={"PATH": f"{ssh_dir}{os.pathsep}{os.environ['PATH']}", "SSH_CAPTURE": str(ssh_log)},
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "WARN ssh.dev-web-01.reachability" in result.stdout
    assert "summary:" in result.stdout
    assert ssh_log.read_text(encoding="utf-8")
    captured = ssh_log.read_text(encoding="utf-8")
    assert "-i" not in captured
    assert "IdentityFile" not in captured


def test_dns_mismatch_is_warning_class_in_native_tasks() -> None:
    tasks_file = TASKS_FILE.read_text(encoding="utf-8")

    assert "ansible.builtin.slurp:" in tasks_file
    assert "ansible.builtin.command: resolvectl dns" in tasks_file
    assert "pve_guest_dns_present" in tasks_file
    assert "severity: \"{{ 'PASS' if pve_guest_dns_present else 'WARN' }}\"" in tasks_file
    assert "WARN') ~ ' guest.' ~ pve_guest_name ~ '.dns.'" in tasks_file
