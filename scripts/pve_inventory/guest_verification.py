"""Read-only verification for repo-managed PVE guests.

The live workflow is intentionally explicit and uses the generated Ansible
inventory as the source of truth for guest SSH targets, tags, and metadata.
It does not read private keys or mutate guests.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, cast

from .errors import ValidationError, require
from .io import load_yaml
from .paths import DEFAULT_ANSIBLE
from .preflight_results import CheckResult, Severity, has_failures, render_report


SSHRunner = Callable[..., Any]


@dataclass(frozen=True)
class GuestTarget:
    """One generated-inventory host that should be verified."""

    name: str
    hostvars: dict[str, Any]


def parse_args(argv: list[str]) -> argparse.Namespace:
    """Parse CLI flags for the explicit guest verification command."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", type=Path, default=DEFAULT_ANSIBLE, help="Path to the generated PVE inventory")
    parser.add_argument("--group", default="pve_vms", help="Inventory group to verify")
    return parser.parse_args(argv)


def _emit(results: list[CheckResult], severity: Severity, check_id: str, message: str) -> None:
    results.append(CheckResult(severity=severity, check_id=check_id, message=message))


def _inventory_hosts(inventory: dict[str, Any], group: str) -> list[GuestTarget]:
    inventory_all = inventory.get("all")
    require(isinstance(inventory_all, dict), "inventory: expected all to be a mapping")
    children = cast(dict[str, Any], inventory_all).get("children", {})
    require(isinstance(children, dict), "inventory: expected all.children to be a mapping")
    target_group = children.get(group)
    if target_group is None:
        return []
    require(isinstance(target_group, dict), f"inventory: expected {group} to be a mapping")
    hosts = target_group.get("hosts", {})
    require(isinstance(hosts, dict), f"inventory: expected {group}.hosts to be a mapping")
    return [GuestTarget(name=name, hostvars=hostvars if isinstance(hostvars, dict) else {}) for name, hostvars in hosts.items()]


def _remote_script() -> str:
    return (
        "set +e; "
        "printf 'hostname=%s\\n' \"$(hostname -s 2>/dev/null || hostname 2>/dev/null || true)\"; "
        "printf 'ips=%s\\n' \"$(hostname -I 2>/dev/null || true)\"; "
        "if command -v systemctl >/dev/null 2>&1; then "
        "printf 'qga_loadstate=%s\\n' \"$(systemctl show -p LoadState --value qemu-guest-agent.service 2>/dev/null || true)\"; "
        "printf 'qga_active=%s\\n' \"$(systemctl show -p ActiveState --value qemu-guest-agent.service 2>/dev/null || true)\"; "
        "else printf 'qga_loadstate=unknown\\nqga_active=unknown\\n'; fi; "
        "if sudo -n true >/dev/null 2>&1; then printf 'sudo_n_true=ok\\n'; else printf 'sudo_n_true=denied\\n'; fi; "
        "permitrootlogin=unknown; "
        "if command -v sshd >/dev/null 2>&1; then permitrootlogin=\"$(sshd -T 2>/dev/null | sed -n 's/^permitrootlogin //p' | head -n1)\"; fi; "
        "printf 'permitrootlogin=%s\\n' \"${permitrootlogin:-unknown}\"; "
        "if [ -r /etc/resolv.conf ]; then "
        "nameservers=; "
        "while read -r keyword value _rest; do [ \"$keyword\" = nameserver ] || continue; nameservers=\"${nameservers}${nameservers:+,}$value\"; done </etc/resolv.conf; "
        "printf 'resolv_conf_nameservers=%s\\n' \"$nameservers\"; "
        "fi; "
        "if command -v resolvectl >/dev/null 2>&1; then printf 'resolvectl_dns=%s\\n' \"$(resolvectl dns 2>/dev/null | tr '\n' ';')\"; fi; "
        "exit 0"
    )


def _ssh_command(host: str, ssh_user: str) -> list[str]:
    return [
        "ssh",
        "-o",
        "BatchMode=yes",
        "-o",
        "ConnectTimeout=10",
        "-o",
        "PasswordAuthentication=no",
        "-o",
        "KbdInteractiveAuthentication=no",
        f"{ssh_user}@{host}",
        "sh",
        "-lc",
        _remote_script(),
    ]


def _parse_key_values(text: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in text.splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def _local_inventory_checks(target: GuestTarget, results: list[CheckResult]) -> bool:
    hostvars = target.hostvars
    ok = True

    ansible_user = hostvars.get("ansible_user")
    if ansible_user == "ops":
        _emit(results, "PASS", f"inventory.{target.name}.user", "ansible_user is ops")
    else:
        _emit(results, "FAIL", f"inventory.{target.name}.user", f"ansible_user must be ops, got {ansible_user!r}")
        ok = False

    if hostvars.get("ansible_connection") == "ssh":
        _emit(results, "PASS", f"inventory.{target.name}.connection", "ansible_connection is ssh")
    else:
        _emit(results, "FAIL", f"inventory.{target.name}.connection", f"ansible_connection must be ssh, got {hostvars.get('ansible_connection')!r}")
        ok = False

    if hostvars.get("ansible_become") is False:
        _emit(results, "PASS", f"inventory.{target.name}.become", "ansible_become is false")
    else:
        _emit(results, "FAIL", f"inventory.{target.name}.become", f"ansible_become must be false, got {hostvars.get('ansible_become')!r}")
        ok = False

    if hostvars.get("ansible_become_method") == "sudo":
        _emit(results, "PASS", f"inventory.{target.name}.become_method", "ansible_become_method is sudo")
    else:
        _emit(results, "FAIL", f"inventory.{target.name}.become_method", f"ansible_become_method must be sudo, got {hostvars.get('ansible_become_method')!r}")
        ok = False

    pve_groups = hostvars.get("pve_ansible_groups", [])
    if isinstance(pve_groups, list):
        inventory_groups = {name for name, group in hostvars.get("__all_children__", {}).items() if isinstance(group, dict) and target.name in (group.get("hosts") or {}) and name not in {"pve_vms"}}
        missing = [group for group in pve_groups if group not in inventory_groups]
        if missing:
            _emit(results, "FAIL", f"inventory.{target.name}.groups", f"inventory is missing expected group(s): {', '.join(missing)}")
            ok = False
        else:
            _emit(results, "PASS", f"inventory.{target.name}.groups", f"inventory groups cover {len(pve_groups)} declared group(s)")
    else:
        _emit(results, "FAIL", f"inventory.{target.name}.groups", "pve_ansible_groups must be a list")
        ok = False

    if isinstance(hostvars.get("pve_tags"), list):
        _emit(results, "PASS", f"inventory.{target.name}.tags", f"inventory exposes {len(hostvars['pve_tags'])} declared tag(s)")
    else:
        _emit(results, "FAIL", f"inventory.{target.name}.tags", "pve_tags must be a list")
        ok = False

    return ok


def _run_ssh_checks(target: GuestTarget, results: list[CheckResult], ssh_runner: SSHRunner) -> None:
    host = target.hostvars.get("ansible_host")
    if not isinstance(host, str) or not host:
        _emit(results, "FAIL", f"ssh.{target.name}.target", "ansible_host must be a non-empty string")
        return

    ssh_user = target.hostvars.get("ansible_user") or "ops"
    command = _ssh_command(host, str(ssh_user))
    try:
        completed = ssh_runner(command, check=False, capture_output=True, text=True, timeout=20)
    except FileNotFoundError:
        _emit(results, "FAIL", f"ssh.{target.name}.command", "ssh command is unavailable")
        return
    except subprocess.TimeoutExpired:
        _emit(results, "WARN", f"ssh.{target.name}.reachability", f"{host} did not respond before the SSH timeout")
        return
    except subprocess.SubprocessError as exc:
        _emit(results, "WARN", f"ssh.{target.name}.reachability", f"{host} is unreachable: {exc}")
        return

    if completed.returncode != 0:
        stderr = (completed.stderr or completed.stdout or "").strip().splitlines()[:1]
        detail = stderr[0] if stderr else f"exit {completed.returncode}"
        _emit(results, "WARN", f"ssh.{target.name}.reachability", f"{host} is unreachable or unauthorized: {detail}")
        return

    values = _parse_key_values(completed.stdout or "")
    expected_hostname = target.name
    actual_hostname = values.get("hostname", "")
    if actual_hostname == expected_hostname:
        _emit(results, "PASS", f"guest.{target.name}.hostname", f"hostname matches {expected_hostname}")
    else:
        _emit(results, "FAIL", f"guest.{target.name}.hostname", f"hostname mismatch: expected {expected_hostname}, got {actual_hostname or 'unknown'}")

    declared_ip = str(host)
    remote_ips = set((values.get("ips", "") or "").split())
    if declared_ip in remote_ips:
        _emit(results, "PASS", f"guest.{target.name}.ip", f"declared static IP {declared_ip} is present")
    else:
        _emit(results, "FAIL", f"guest.{target.name}.ip", f"declared static IP {declared_ip} is not present in guest IPs {sorted(remote_ips)!r}")

    qga_loadstate = (values.get("qga_loadstate") or "").strip().lower()
    qga_active = (values.get("qga_active") or "").strip().lower()
    if qga_loadstate == "loaded" and qga_active == "active":
        _emit(results, "PASS", f"guest.{target.name}.qemu-guest-agent", "qemu-guest-agent is loaded and active")
    else:
        _emit(results, "FAIL", f"guest.{target.name}.qemu-guest-agent", f"qemu-guest-agent is not active/visible (LoadState={qga_loadstate or 'unknown'}, ActiveState={qga_active or 'unknown'})")

    if values.get("sudo_n_true") == "ok":
        _emit(results, "PASS", f"guest.{target.name}.sudo", "ops can run sudo -n true")
    else:
        _emit(results, "FAIL", f"guest.{target.name}.sudo", "ops cannot run sudo -n true")

    permitrootlogin = (values.get("permitrootlogin") or "unknown").strip().lower()
    if permitrootlogin in {"no", "prohibit-password", "forced-commands-only"}:
        _emit(results, "PASS", f"guest.{target.name}.root-ssh", f"effective sshd config disables root login ({permitrootlogin})")
    elif permitrootlogin == "unknown":
        _emit(results, "WARN", f"guest.{target.name}.root-ssh", "effective sshd config could not be inspected")
    else:
        _emit(results, "FAIL", f"guest.{target.name}.root-ssh", f"effective sshd config allows root login ({permitrootlogin})")

    expected_dns = [str(item) for item in target.hostvars.get("pve_dns", []) if item]
    resolver_blob = "\n".join(filter(None, [values.get("resolv_conf_nameservers", ""), values.get("resolvectl_dns", "")]))
    missing_dns = [name for name in expected_dns if name not in resolver_blob]
    if not expected_dns:
        _emit(results, "SKIP", f"guest.{target.name}.dns", "no declared DNS entries to verify")
    elif missing_dns:
        _emit(results, "WARN", f"guest.{target.name}.dns", f"resolver config does not expose declared DNS server(s): {', '.join(missing_dns)}")
    else:
        _emit(results, "PASS", f"guest.{target.name}.dns", "resolver config exposes declared DNS server(s)")


def run_guest_verification(
    *,
    inventory_path: Path = DEFAULT_ANSIBLE,
    group: str = "pve_vms",
    ssh_runner: SSHRunner = subprocess.run,
) -> list[CheckResult]:
    """Verify repo-managed guests without mutating them."""

    results: list[CheckResult] = []
    try:
        inventory = load_yaml(inventory_path)
        inventory_all_raw = inventory.get("all")
        require(isinstance(inventory_all_raw, dict), "inventory: expected all to be a mapping")
        inventory_all = cast(dict[str, Any], inventory_all_raw)
        children = inventory_all.get("children", {})
        require(isinstance(children, dict), "inventory: expected all.children to be a mapping")
        targets = _inventory_hosts(inventory, group)
    except ValidationError as exc:
        _emit(results, "FAIL", "inventory.load", str(exc))
        return results

    if not targets:
        _emit(results, "SKIP", f"inventory.{group}", f"no declared guests found in generated inventory group {group}")
        return results

    for target in targets:
        target.hostvars.setdefault("__all_children__", children)
        _local_inventory_checks(target, results)
        if isinstance(target.hostvars.get("ansible_host"), str) and target.hostvars.get("ansible_user") == "ops":
            _run_ssh_checks(target, results, ssh_runner)
    return results


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint for the canonical guest verification command."""

    args = parse_args(sys.argv[1:] if argv is None else argv)
    results = run_guest_verification(inventory_path=args.inventory, group=args.group)
    print(render_report(results), end="")
    return 1 if has_failures(results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
