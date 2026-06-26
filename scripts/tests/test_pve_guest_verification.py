"""Tests for the explicit PVE guest verification workflow."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from scripts.pve_inventory.guest_verification import run_guest_verification
from scripts.pve_inventory.io import load_yaml
from scripts.pve_inventory.preflight_results import has_failures, render_report


ROOT = Path(__file__).resolve().parents[2]
INVENTORY_PATH = ROOT / "ansible" / "inventories" / "generated" / "pve.yml"
MAKEFILE_PATH = ROOT / "Makefile"
MODULE_MAKEFILE_PATH = ROOT / "infra" / "tofu" / "pve" / "Makefile"
WORKFLOW_PATH = ROOT / ".github" / "workflows" / "offline-validation.yml"


def _inventory(hosts: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return {
        "all": {
            "children": {
                "pve_vms": {"hosts": hosts},
                "dev": {"hosts": {name: {} for name, host in hosts.items() if "dev" in host.get("pve_tags", [])}},
                "web": {"hosts": {name: {} for name, host in hosts.items() if "web" in host.get("pve_tags", [])}},
            }
        }
    }


def _write_inventory(tmp_path: Path, doc: dict[str, Any]) -> Path:
    path = tmp_path / "pve.yml"
    import yaml

    path.write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")
    return path


def _ok_payload(hostname: str, ip: str, dns: str = "10.10.0.254", *, qga: bool = True, root_login: str = "no") -> str:
    parts = [
        f"hostname={hostname}",
        f"ips={ip}",
        f"qga_loadstate={'loaded' if qga else 'not-found'}",
        f"qga_active={'active' if qga else 'inactive'}",
        "sudo_n_true=ok",
        f"permitrootlogin={root_login}",
        f"resolv_conf_nameservers={dns}",
        f"resolvectl_dns={dns};",
    ]
    return "\n".join(parts) + "\n"


def test_generated_inventory_assumptions_are_present() -> None:
    inventory = load_yaml(INVENTORY_PATH)
    hosts = inventory["all"]["children"]["pve_vms"]["hosts"]

    assert set(hosts) == {"dev-web-01", "prod-app-01", "media-lab-01"}
    for hostvars in hosts.values():
        assert hostvars["ansible_user"] == "ops"
        assert hostvars["ansible_connection"] == "ssh"
        assert hostvars["ansible_become"] is False
        assert hostvars["ansible_become_method"] == "sudo"
        assert isinstance(hostvars["pve_ansible_groups"], list) and hostvars["pve_ansible_groups"]
        assert isinstance(hostvars["pve_tags"], list) and hostvars["pve_tags"]
        assert isinstance(hostvars["pve_dns"], list) and hostvars["pve_dns"]


def test_no_guests_reports_skip_and_exits_cleanly(tmp_path: Path) -> None:
    inventory_path = _write_inventory(tmp_path, {"all": {"children": {"pve_vms": {"hosts": {}}}}})
    ssh_calls: list[list[str]] = []

    def runner(command: list[str], **_: Any) -> subprocess.CompletedProcess[str]:
        ssh_calls.append(command)
        raise AssertionError("ssh should not be called when there are no generated guests")

    results = run_guest_verification(inventory_path=inventory_path, ssh_runner=runner)

    assert not has_failures(results)
    assert not ssh_calls
    assert "SKIP inventory.pve_vms" in render_report(results)


def test_unreachable_guest_reports_warn_and_continues(tmp_path: Path) -> None:
    inventory_path = _write_inventory(
        tmp_path,
        _inventory(
            {
                "dev-web-01": {
                    "ansible_host": "10.10.0.20",
                    "ansible_user": "ops",
                    "ansible_connection": "ssh",
                    "ansible_become": False,
                    "ansible_become_method": "sudo",
                    "pve_dns": ["10.10.0.254"],
                    "pve_ansible_groups": ["dev", "web"],
                    "pve_tags": ["dev", "web"],
                }
            }
        ),
    )
    ssh_calls: list[list[str]] = []

    def runner(command: list[str], **_: Any) -> subprocess.CompletedProcess[str]:
        ssh_calls.append(command)
        return subprocess.CompletedProcess(command, 255, stdout="", stderr="Permission denied (publickey).")

    results = run_guest_verification(inventory_path=inventory_path, ssh_runner=runner)

    assert not has_failures(results)
    assert ssh_calls and ssh_calls[0][0] == "ssh"
    assert all("-i" not in part for part in ssh_calls[0])
    assert any(result.severity == "WARN" and result.check_id == "ssh.dev-web-01.reachability" for result in results)


def test_dns_mismatch_is_warned_for_reachable_guest(tmp_path: Path) -> None:
    inventory_path = _write_inventory(
        tmp_path,
        _inventory(
            {
                "dev-web-01": {
                    "ansible_host": "10.10.0.20",
                    "ansible_user": "ops",
                    "ansible_connection": "ssh",
                    "ansible_become": False,
                    "ansible_become_method": "sudo",
                    "pve_dns": ["10.10.0.254"],
                    "pve_ansible_groups": ["dev", "web"],
                    "pve_tags": ["dev", "web"],
                }
            }
        ),
    )

    def runner(command: list[str], **_: Any) -> subprocess.CompletedProcess[str]:
        assert command[0] == "ssh"
        return subprocess.CompletedProcess(
            command,
            0,
            stdout=_ok_payload("dev-web-01", "10.10.0.20", dns="1.1.1.1"),
            stderr="",
        )

    results = run_guest_verification(inventory_path=inventory_path, ssh_runner=runner)

    assert not has_failures(results)
    assert any(result.severity == "WARN" and result.check_id == "guest.dev-web-01.dns" for result in results)


def test_reachable_guest_passes_without_printing_secret_material(tmp_path: Path) -> None:
    inventory_path = _write_inventory(
        tmp_path,
        _inventory(
            {
                "dev-web-01": {
                    "ansible_host": "10.10.0.20",
                    "ansible_user": "ops",
                    "ansible_connection": "ssh",
                    "ansible_become": False,
                    "ansible_become_method": "sudo",
                    "pve_dns": ["10.10.0.254"],
                    "pve_ansible_groups": ["dev", "web"],
                    "pve_tags": ["dev", "web"],
                }
            }
        ),
    )
    ssh_calls: list[list[str]] = []

    def runner(command: list[str], **_: Any) -> subprocess.CompletedProcess[str]:
        ssh_calls.append(command)
        return subprocess.CompletedProcess(command, 0, stdout=_ok_payload("dev-web-01", "10.10.0.20"), stderr="")

    results = run_guest_verification(inventory_path=inventory_path, ssh_runner=runner)
    report = render_report(results)

    assert not has_failures(results)
    assert "FAIL" not in report
    assert "private key" not in report.lower()
    assert "token_secret" not in report.lower()
    assert all("-i" not in part for part in ssh_calls[0])
    assert all("id_rsa" not in part and "id_ed25519" not in part for part in ssh_calls[0])


def test_make_check_and_offline_ci_do_not_invoke_guest_verification() -> None:
    make_text = MAKEFILE_PATH.read_text(encoding="utf-8")
    module_make_text = MODULE_MAKEFILE_PATH.read_text(encoding="utf-8")
    workflow_text = WORKFLOW_PATH.read_text(encoding="utf-8")

    assert "check: check-generated test lint-yaml tofu-fmt tofu-validate" in make_text
    assert "pve-verify-guests:" in make_text
    assert "pve-ansible-check:" in make_text and "$(MAKE) pve-verify-guests" in make_text
    assert "pve-verify-guests" not in workflow_text
    assert "python -m scripts.pve_inventory.guest_verification" in module_make_text
    assert "ansible-check: verify-guests" in module_make_text
    assert "verify-guests-syntax" in module_make_text and "--syntax-check" in module_make_text
